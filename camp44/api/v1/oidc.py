"""
OIDC authentication router.
"""
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from camp44.api import deps_async
from camp44.core.config import settings
from camp44.core.oauth import oauth
from camp44.core.security import create_access_token
from camp44.crud import user_async as user_crud

router = APIRouter()


@router.get("/login")
async def oidc_login(request: Request):
    """
    Initiate OIDC login flow.
    """
    if not settings.OAUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC authentication not configured"
        )

    # Redirect to OIDC provider's authorization endpoint
    redirect_uri = request.url_for('oidc_callback')
    return await oauth.oidc.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def oidc_callback(
    request: Request,
    db: AsyncSession = Depends(deps_async.get_db)
):
    """
    Handle OIDC callback after user authentication.
    """
    if not settings.OAUTH_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC authentication not configured"
        )

    try:
        # Get token and user info from OIDC provider
        token = await oauth.oidc.authorize_access_token(request)
        user_info = token.get('userinfo')
        
        if not user_info:
            # If userinfo not included in token, fetch it using userinfo endpoint
            user_info = await oauth.oidc.parse_id_token(request, token)
        
        # Extract user data from OIDC claims
        oidc_sub = user_info.get('sub')
        email = user_info.get('email')
        email_verified = user_info.get('email_verified', False)
        name = user_info.get('name') or user_info.get('preferred_username')
        tenant_id = user_info.get(settings.OIDC_TENANT_CLAIM)
        
        if not oidc_sub or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid user info from identity provider"
            )
        
        # Find or create user by OIDC sub
        user = await user_crud.get_by_oidc_sub(db, oidc_sub=oidc_sub)
        
        if not user:
            # Check if user exists with same email
            existing_user = await user_crud.get_by_email(db, email=email)
            
            if existing_user:
                # Link OIDC to existing user
                user = existing_user
                user.oidc_sub = oidc_sub
                user.oidc_issuer = settings.OIDC_ISSUER_URL
                user.oidc_email_verified = email_verified
                user.tenant_id = tenant_id
            else:
                # Create new user
                user = await user_crud.create_oidc_user(
                    db,
                    email=email,
                    display_name=name,
                    oidc_sub=oidc_sub,
                    oidc_issuer=settings.OIDC_ISSUER_URL,
                    oidc_email_verified=email_verified,
                    tenant_id=tenant_id,
                    roles=["user"],
                )
        
        # Create JWT access token
        access_token = create_access_token(
            data={"sub": str(user.id)},
        )
        
        # Set up redirect URL with token - typically to frontend
        redirect_url = f"/auth-callback?token={access_token}"
        
        return RedirectResponse(redirect_url)
    
    except Exception as e:
        # Log the error
        print(f"OIDC Callback error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to authenticate: {str(e)}"
        )


@router.get("/userinfo")
async def oidc_userinfo(
    request: Request,
    db: AsyncSession = Depends(deps_async.get_db),
    current_user = Depends(deps_async.get_current_active_user)
) -> Dict:
    """
    Get user info for authenticated user.
    """
    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "roles": current_user.roles,
        "oidc_sub": current_user.oidc_sub,
        "tenant_id": current_user.tenant_id,
        "has_passkeys": len(current_user.passkey_credentials) > 0
    }
