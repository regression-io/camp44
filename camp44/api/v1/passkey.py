"""
WebAuthn/Passkey authentication router.
"""
import base64
import json
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from webauthn.helpers.structs import AuthenticationCredential, RegistrationCredential

from camp44.api import deps_async
from camp44.core.config import settings
from camp44.core.security import create_access_token
from camp44.core.webauthn import (
    generate_passkey_registration_options,
    verify_passkey_registration,
    generate_passkey_authentication_options,
    verify_passkey_authentication,
)
from camp44.crud import user_async as user_crud


router = APIRouter()


# Session storage for challenges - in production use Redis or another secure storage
_CHALLENGES = {}


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


@router.post("/register/options", response_model=PasskeyRegOptionsResponse)
async def passkey_register_options(
    request: PasskeyRegOptionsRequest,
    current_user = Depends(deps_async.get_current_active_user),
    db: AsyncSession = Depends(deps_async.get_db),
):
    """
    Get passkey registration options.
    """
    # Ensure user_id matches current user
    if str(current_user.id) != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register passkeys for your own account"
        )
    
    # Generate registration options
    options = generate_passkey_registration_options(
        user_id=str(current_user.id),
        user_name=current_user.email,
        user_display_name=current_user.display_name or current_user.email,
        existing_credentials=current_user.passkey_credentials
    )
    
    # Store challenge
    challenge_id = str(current_user.id)
    _CHALLENGES[challenge_id] = base64.b64encode(options.challenge).decode('ascii')
    
    # Convert options to dictionary
    options_dict = options.model_dump()
    
    # Base64 encode challenge for client
    options_dict["challenge"] = _CHALLENGES[challenge_id]
    
    return PasskeyRegOptionsResponse(options=options_dict)


@router.post("/register/verify")
async def passkey_register_verify(
    request: PasskeyRegVerifyRequest,
    current_user = Depends(deps_async.get_current_active_user),
    db: AsyncSession = Depends(deps_async.get_db),
):
    """
    Verify passkey registration.
    """
    # Ensure user_id matches current user
    if str(current_user.id) != request.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only register passkeys for your own account"
        )
    
    # Get stored challenge
    challenge_id = str(current_user.id)
    stored_challenge = _CHALLENGES.get(challenge_id)
    if not stored_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration challenge not found or expired"
        )
    
    # Clean up challenge
    del _CHALLENGES[challenge_id]
    
    # Create WebAuthn credential from request
    try:
        credential = RegistrationCredential.model_validate(request.credential)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid credential format: {str(e)}"
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
    user = await user_crud.update(
        db, 
        db_obj=current_user, 
        obj_in={"passkey_credentials": current_credentials}
    )
    
    return {"success": True, "credential_id": credential_data["id"]}


@router.post("/authenticate/options", response_model=PasskeyAuthOptionsResponse)
async def passkey_authenticate_options(
    request: PasskeyAuthOptionsRequest,
    db: AsyncSession = Depends(deps_async.get_db)
):
    """
    Get passkey authentication options.
    """
    # For email-based login, get user's credentials
    user_credentials = []
    user = None
    
    if request.email:
        user = await user_crud.get_by_email(db, email=request.email)
        if user:
            user_credentials = user.passkey_credentials
    
    # Generate authentication options
    options = generate_passkey_authentication_options(user_credentials=user_credentials)
    
    # Store challenge with user ID if known
    challenge_id = str(user.id) if user else "public"
    _CHALLENGES[challenge_id] = base64.b64encode(options.challenge).decode('ascii')
    
    # Convert options to dictionary
    options_dict = options.model_dump()
    
    # Base64 encode challenge for client
    options_dict["challenge"] = _CHALLENGES[challenge_id]
    
    return PasskeyAuthOptionsResponse(options=options_dict)


@router.post("/authenticate/verify", response_model=PasskeyAuthVerifyResponse)
async def passkey_authenticate_verify(
    request: PasskeyAuthVerifyRequest,
    db: AsyncSession = Depends(deps_async.get_db)
):
    """
    Verify passkey authentication.
    """
    # Find the user that owns this credential
    user = None
    credential_data = None
    
    # If email provided, look up user
    if request.email:
        user = await user_crud.get_by_email(db, email=request.email)
        if not user or not user.passkey_credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or no passkeys registered"
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
            auth_credential = AuthenticationCredential.model_validate(request.credential)
            credential_id = base64.b64encode(auth_credential.id).decode('utf-8')
            
            users = await user_crud.get_users_with_passkey(db, credential_id=credential_id)
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
                detail=f"Invalid credential format: {str(e)}"
            )
    
    if not user or not credential_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or credential not found"
        )
    
    # Get stored challenge
    challenge_id = str(user.id)
    stored_challenge = _CHALLENGES.get(challenge_id) or _CHALLENGES.get("public")
    if not stored_challenge:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authentication challenge not found or expired"
        )
    
    # Clean up challenge
    if challenge_id in _CHALLENGES:
        del _CHALLENGES[challenge_id]
    if "public" in _CHALLENGES:
        del _CHALLENGES["public"]
    
    # Create WebAuthn credential from request
    try:
        auth_credential = AuthenticationCredential.model_validate(request.credential)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid credential format: {str(e)}"
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
        await user_crud.update(db, db_obj=user, obj_in={"passkey_credentials": user.passkey_credentials})
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Passkey authentication failed: {str(e)}"
        )
    
    # Create access token
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return PasskeyAuthVerifyResponse(access_token=access_token)
