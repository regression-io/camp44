"""
WebAuthn/Passkey authentication router.
"""

import base64
import json
import logging
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from webauthn.helpers.structs import AuthenticationCredential, RegistrationCredential

from camp44.api import deps
from camp44.core.auth_tokens import create_token_pair
from camp44.core.config import settings
from camp44.core.webauthn import (
    generate_passkey_authentication_options,
    generate_passkey_registration_options,
    verify_passkey_authentication,
    verify_passkey_registration,
)
from camp44.crud import user as user_crud
from camp44.crud.user import _ensure_admin_role

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# In-process challenge store
# ---------------------------------------------------------------------------
# SECURITY (Audit P1-2): the previous implementation was a bare module-level
# ``_CHALLENGES = {}`` dict with no TTL, no single-use semantics, and a single
# ``"public"`` key shared across every concurrent discoverable-auth ceremony
# (so two simultaneous logins overwrote each other). Replays were unbounded;
# concurrent discoverable auths raced; multi-worker deploys silently failed.
#
# This replacement adds:
#   * TTL — challenges expire 5 minutes after issue
#   * single-use — pop_* deletes on success; verify can never reuse a value
#   * a threading.Lock — protects every map access against intra-process race
#   * per-challenge keying for discoverable auth — eliminates the "public"
#     collision; each pending discoverable challenge has its own slot keyed
#     by the challenge value itself
#
# What this does NOT fix:
#   * Cross-worker / cross-replica deployments. The store is process-local,
#     so a challenge generated on worker A is invisible to worker B. Standalone
#     camp44 consumers running multiple workers MUST either pin sessions to a
#     single worker, run a single worker, or replace this store with a shared
#     backend. scalemate-service already does the latter — its
#     ``scalemate_service.services.challenge_store`` is DB-backed — and does
#     not register camp44's passkey router, so this caveat does not apply in
#     the ScaleMate deployment.
# ---------------------------------------------------------------------------

_CHALLENGE_TTL = timedelta(minutes=5)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _b64url_decode(s: str) -> bytes:
    """Decode a base64url string (with or without padding) to bytes."""
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


class _ChallengeStore:
    """Thread-safe in-process challenge store with TTL and single-use semantics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # (user_id_str, ceremony) -> (challenge_b64, expiry)
        self._per_user: Dict[tuple, tuple] = {}
        # challenge_b64 -> expiry  (keyed by challenge so concurrent
        # discoverable ceremonies cannot overwrite each other)
        self._discoverable: Dict[str, datetime] = {}

    def _purge_expired_locked(self) -> None:
        now = _utcnow()
        self._per_user = {k: v for k, v in self._per_user.items() if v[1] > now}
        self._discoverable = {k: v for k, v in self._discoverable.items() if v > now}

    def store_user(self, user_id: str, ceremony: str, challenge_b64: str) -> None:
        with self._lock:
            self._purge_expired_locked()
            self._per_user[(user_id, ceremony)] = (
                challenge_b64,
                _utcnow() + _CHALLENGE_TTL,
            )

    def store_discoverable(self, challenge_b64: str) -> None:
        with self._lock:
            self._purge_expired_locked()
            self._discoverable[challenge_b64] = _utcnow() + _CHALLENGE_TTL

    def pop_user(self, user_id: str, ceremony: str) -> Optional[str]:
        """Atomically remove and return the challenge if unexpired; else None."""
        with self._lock:
            entry = self._per_user.pop((user_id, ceremony), None)
            if entry is None:
                return None
            challenge_b64, expiry = entry
            if expiry <= _utcnow():
                return None
            return challenge_b64

    def pop_discoverable(self, challenge_b64: str) -> bool:
        """Atomically remove the discoverable challenge if present + unexpired."""
        with self._lock:
            expiry = self._discoverable.pop(challenge_b64, None)
            return expiry is not None and expiry > _utcnow()


_store = _ChallengeStore()


class PasskeyRegOptionsRequest(BaseModel):
    """Request model for passkey registration options."""

    user_id: str


class PasskeyRegOptionsResponse(BaseModel):
    """Response model for passkey registration options."""

    options: Dict


class PasskeyRegVerifyRequest(BaseModel):
    """Request model for passkey registration verification."""

    user_id: str
    credential: Dict


class PasskeyAuthOptionsRequest(BaseModel):
    """Request model for passkey authentication options."""

    email: Optional[str] = None


class PasskeyAuthOptionsResponse(BaseModel):
    """Response model for passkey authentication options."""

    options: Dict


class PasskeyAuthVerifyRequest(BaseModel):
    """Request model for passkey authentication verification."""

    credential: Dict
    email: Optional[str] = None
    credential_id: Optional[str] = None


class PasskeyAuthVerifyResponse(BaseModel):
    """Response model for passkey authentication verification."""

    access_token: str
    token_type: str = "bearer"
    refresh_token: Optional[str] = None
    expires_in: int = 900


@router.post("/register/options", response_model=PasskeyRegOptionsResponse)
def passkey_register_options(
    request: PasskeyRegOptionsRequest,
    current_user=Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """
    Get passkey registration options.
    """
    # Ensure user_id matches current user
    if str(current_user.id) != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register passkeys for your own account",
        )

    # Generate registration options
    options = generate_passkey_registration_options(
        user_id=str(current_user.id),
        user_name=current_user.email,
        user_display_name=current_user.display_name or current_user.email,
        existing_credentials=current_user.passkey_credentials,
    )

    # Store challenge — TTL + single-use, keyed by (user_id, "registration")
    challenge_b64 = base64.b64encode(options.challenge).decode("ascii")
    _store.store_user(str(current_user.id), "registration", challenge_b64)

    # Convert options to dictionary
    options_dict = options.model_dump()

    # Base64 encode challenge for client
    options_dict["challenge"] = challenge_b64

    return PasskeyRegOptionsResponse(options=options_dict)


@router.post("/register/verify")
def passkey_register_verify(
    request: PasskeyRegVerifyRequest,
    current_user=Depends(deps.get_current_active_user),
    db: Session = Depends(deps.get_db),
):
    """
    Verify passkey registration.
    """
    # Ensure user_id matches current user
    if str(current_user.id) != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register passkeys for your own account",
        )

    # Atomically retrieve and consume the challenge (TTL + single-use).
    stored_challenge = _store.pop_user(str(current_user.id), "registration")
    if not stored_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration challenge not found or expired",
        )

    # Create WebAuthn credential from request
    try:
        credential = RegistrationCredential.model_validate(request.credential)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid credential format: {str(e)}",
        )

    # Verify registration
    credential_data = verify_passkey_registration(
        credential=credential,
        expected_challenge=base64.b64decode(stored_challenge),
        expected_origin=settings.WEBAUTHN_ORIGIN,
        expected_rp_id=settings.WEBAUTHN_RP_ID,
    )

    # Store credential in user profile
    current_credentials = current_user.passkey_credentials or []
    current_credentials.append(credential_data)

    # Update user
    user = user_crud.update(
        db, db_obj=current_user, obj_in={"passkey_credentials": current_credentials}
    )

    return {"success": True, "credential_id": credential_data["id"]}


@router.post("/authenticate/options", response_model=PasskeyAuthOptionsResponse)
def passkey_authenticate_options(
    request: PasskeyAuthOptionsRequest, db: Session = Depends(deps.get_db)
):
    """
    Get passkey authentication options.
    """
    # For email-based login, get user's credentials
    user_credentials = []
    user = None

    if request.email:
        user = user_crud.get_user_by_email(db, email=request.email)
        if user:
            user_credentials = user.passkey_credentials

    # Generate authentication options
    options = generate_passkey_authentication_options(user_credentials=user_credentials)

    # Store challenge. For email-based auth we key by user id; for
    # discoverable auth (no email) we key by the challenge value itself, so
    # concurrent ceremonies cannot overwrite each other (previous behavior
    # used a shared "public" slot and one login would invalidate another).
    challenge_b64 = base64.b64encode(options.challenge).decode("ascii")
    if user is not None:
        _store.store_user(str(user.id), "authentication", challenge_b64)
    else:
        _store.store_discoverable(challenge_b64)

    # Convert options to dictionary
    options_dict = options.model_dump()

    # Base64 encode challenge for client
    options_dict["challenge"] = challenge_b64

    return PasskeyAuthOptionsResponse(options=options_dict)


@router.post("/authenticate/verify", response_model=PasskeyAuthVerifyResponse)
def passkey_authenticate_verify(
    request: PasskeyAuthVerifyRequest, db: Session = Depends(deps.get_db)
):
    """
    Verify passkey authentication.
    """
    # Find the user that owns this credential
    user = None
    credential_data = None

    # If email provided, look up user
    if request.email:
        user = user_crud.get_user_by_email(db, email=request.email)
        if not user or not user.passkey_credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or no passkeys registered",
            )

        # Find matching credential
        for cred in user.passkey_credentials:
            if cred["id"] == request.credential_id:
                credential_data = cred
                break
    else:
        # Search all users for credential - discoverable credentials flow
        # Create WebAuthn credential from request
        try:
            auth_credential = AuthenticationCredential.model_validate(
                request.credential
            )
            credential_id = base64.b64encode(auth_credential.id).decode("utf-8")

            users = user_crud.get_users_with_passkey(db, credential_id=credential_id)
            if users and len(users) > 0:
                user = users[0]

                # Find matching credential
                for cred in user.passkey_credentials:
                    if cred["id"] == credential_id:
                        credential_data = cred
                        break
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid credential format: {str(e)}",
            )

    if not user or not credential_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or credential not found",
        )

    # Recover and consume the challenge. Two paths:
    #   * email-based: stored under (user.id, "authentication") at /options
    #   * discoverable: stored keyed by challenge value itself. We extract the
    #     value the client claims to have signed from clientDataJSON and look
    #     it up in the pending discoverable set. The webauthn library then
    #     re-verifies the assertion signature against that same value below.
    stored_challenge = _store.pop_user(str(user.id), "authentication")
    if stored_challenge is None:
        # Discoverable path — find the challenge the client signed.
        try:
            client_data = json.loads(
                AuthenticationCredential.model_validate(
                    request.credential
                ).response.client_data_json.decode("utf-8")
            )
            claimed_b64url = client_data.get("challenge", "")
            claimed_bytes = _b64url_decode(claimed_b64url)
            claimed_b64 = base64.b64encode(claimed_bytes).decode("ascii")
        except Exception:
            claimed_b64 = ""
        if not claimed_b64 or not _store.pop_discoverable(claimed_b64):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Authentication challenge not found or expired",
            )
        stored_challenge = claimed_b64

    # Create WebAuthn credential from request
    try:
        auth_credential = AuthenticationCredential.model_validate(request.credential)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid credential format: {str(e)}",
        )

    # Verify authentication
    try:
        new_sign_count = verify_passkey_authentication(
            credential=auth_credential,
            expected_challenge=base64.b64decode(stored_challenge),
            expected_origin=settings.WEBAUTHN_ORIGIN,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            credential_public_key=base64.b64decode(credential_data["public_key"]),
            credential_current_sign_count=credential_data["sign_count"],
        )

        # Update sign count in stored credential
        for i, cred in enumerate(user.passkey_credentials):
            if cred["id"] == credential_data["id"]:
                user.passkey_credentials[i]["sign_count"] = new_sign_count
                break

        # Update user
        user_crud.update(
            db, db_obj=user, obj_in={"passkey_credentials": user.passkey_credentials}
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Passkey authentication failed: {str(e)}",
        )

    # Auto-promote admin-domain users on login (matches password auth path)
    _ensure_admin_role(user, db)

    # Create token pair
    token_pair = create_token_pair(db, user)

    return PasskeyAuthVerifyResponse(
        access_token=token_pair.access_token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.expires_in,
    )
