"""
WebAuthn/Passkey client and utilities.
"""
import base64
import os
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException, status
import webauthn
from webauthn import generate_registration_options, verify_registration_response
from webauthn import generate_authentication_options, verify_authentication_response
from webauthn.helpers import generate_challenge
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticationCredential,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialCreationOptions,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialRequestOptions,
    RegistrationCredential,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from camp44.core.config import settings


def generate_passkey_registration_options(
    user_id: str,
    user_name: str,
    user_display_name: str,
    existing_credentials: List[Dict] = None,
) -> PublicKeyCredentialCreationOptions:
    """
    Generate registration options for WebAuthn passkey enrollment.
    
    Args:
        user_id: User's unique ID
        user_name: User's name/username (typically email)
        user_display_name: User's display name
        existing_credentials: List of existing credentials to exclude
        
    Returns:
        WebAuthn registration options for client
    """
    # Convert existing credentials to format expected by WebAuthn
    exclude_credentials = []
    if existing_credentials:
        for cred in existing_credentials:
            if 'id' in cred and 'type' in cred:
                try:
                    credential_id = base64.b64decode(cred['id'])
                    exclude_credentials.append(
                        PublicKeyCredentialDescriptor(
                            id=credential_id,
                            type=cred['type'],
                        )
                    )
                except Exception:
                    pass
    
    # Create options
    options = generate_registration_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        rp_name=settings.WEBAUTHN_RP_NAME,
        user_id=user_id,
        user_name=user_name,
        user_display_name=user_display_name,
        challenge=generate_challenge(),
        exclude_credentials=exclude_credentials,
        authenticator_selection=AuthenticatorSelectionCriteria(
            authenticator_attachment=AuthenticatorAttachment.PLATFORM_OR_CROSS_PLATFORM,
            resident_key=ResidentKeyRequirement.PREFERRED,
            user_verification=UserVerificationRequirement.PREFERRED,
        ),
        attestation=AttestationConveyancePreference.NONE,
    )
    
    return options


def verify_passkey_registration(
    credential: RegistrationCredential, 
    expected_challenge: bytes,
    expected_origin: str = None,
    expected_rp_id: str = None,
) -> Dict:
    """
    Verify WebAuthn registration response.
    
    Args:
        credential: WebAuthn registration credential from client
        expected_challenge: Expected challenge bytes
        expected_origin: Expected origin URL
        expected_rp_id: Expected Relying Party ID
        
    Returns:
        Credential information for storage
    """
    origin = expected_origin or settings.WEBAUTHN_ORIGIN
    rp_id = expected_rp_id or settings.WEBAUTHN_RP_ID
    
    try:
        # Verify registration response
        verification = verify_registration_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_origin=origin,
            expected_rp_id=rp_id,
        )
        
        # Create credential info for storage
        credential_info = {
            "id": base64.b64encode(verification.credential_id).decode('utf-8'),
            "public_key": base64.b64encode(verification.credential_public_key).decode('utf-8'),
            "sign_count": verification.sign_count,
            "aaguid": verification.aaguid.hex() if verification.aaguid else None,
            "type": "public-key",
            "transports": list(credential.response.transports) if credential.response.transports else [],
            "created_at": str(verification.credential_creation_time) if verification.credential_creation_time else None,
        }
        
        return credential_info
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Passkey registration failed: {str(e)}"
        )


def generate_passkey_authentication_options(
    user_credentials: List[Dict] = None,
    user_verification: UserVerificationRequirement = UserVerificationRequirement.PREFERRED,
) -> PublicKeyCredentialRequestOptions:
    """
    Generate authentication options for WebAuthn passkey login.
    
    Args:
        user_credentials: List of user's registered credentials
        user_verification: User verification requirement
        
    Returns:
        WebAuthn authentication options for client
    """
    # Convert stored credentials to format expected by WebAuthn
    allow_credentials = []
    if user_credentials:
        for cred in user_credentials:
            try:
                credential_id = base64.b64decode(cred['id'])
                allow_credentials.append(
                    PublicKeyCredentialDescriptor(
                        id=credential_id, 
                        type="public-key",
                    )
                )
            except Exception:
                pass
    
    # Create options
    options = generate_authentication_options(
        rp_id=settings.WEBAUTHN_RP_ID,
        challenge=generate_challenge(),
        allow_credentials=allow_credentials or None,
        user_verification=user_verification,
        timeout=settings.WEBAUTHN_TIMEOUT,
    )
    
    return options


def verify_passkey_authentication(
    credential: AuthenticationCredential,
    expected_challenge: bytes,
    expected_origin: str,
    expected_rp_id: str,
    credential_public_key: bytes,
    credential_current_sign_count: int,
) -> int:
    """
    Verify WebAuthn authentication assertion.
    
    Args:
        credential: WebAuthn authentication credential from client
        expected_challenge: Expected challenge bytes
        expected_origin: Expected origin URL
        expected_rp_id: Expected Relying Party ID
        credential_public_key: Public key for the credential
        credential_current_sign_count: Current signature count
        
    Returns:
        New signature count
    """
    try:
        # Verify authentication response
        verification = verify_authentication_response(
            credential=credential,
            expected_challenge=expected_challenge,
            expected_origin=expected_origin,
            expected_rp_id=expected_rp_id,
            credential_public_key=credential_public_key,
            credential_current_sign_count=credential_current_sign_count,
        )
        
        return verification.new_sign_count
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Passkey authentication failed: {str(e)}"
        )
