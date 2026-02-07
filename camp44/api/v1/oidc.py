"""
OIDC authentication router.
"""
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from camp44.api import deps
from camp44.core.auth_tokens import create_token_pair
from camp44.core.config import settings
from camp44.core.oauth import oauth
from camp44.crud import user as user_crud

router = APIRouter()


@router.get("/login")
async def oidc_login(request: Request):
    """
    Initiate OIDC login flow.
    """
    if not settings.OAUTH_ENABLED:
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={"detail": "OIDC authentication not configured"}
        )

    # Store the frontend callback URL in session for use after OIDC callback
    from_url = request.query_params.get('from_url')
    if from_url:
        from camp44.api.v1.endpoints.auth import _sanitize_redirect_url
        from_url = _sanitize_redirect_url(from_url)
        if from_url:
            request.session['oidc_from_url'] = from_url

    # Redirect to OIDC provider's authorization endpoint
    redirect_uri = request.url_for('oidc_callback')
    # authorize_redirect is async in authlib's Starlette integration
    response = await oauth.oidc.authorize_redirect(request, redirect_uri)
    return response


@router.get("/callback")
async def oidc_callback(
        request: Request,
        db: Session = Depends(deps.get_db)
):
    """
    Handle OIDC callback after user authentication.
    """
    if not settings.OAUTH_ENABLED:
        return JSONResponse(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            content={"detail": "OIDC authentication not configured"}
        )

    try:
        # Get token and user info from OIDC provider
        # authorize_access_token is async in authlib's Starlette integration
        token = await oauth.oidc.authorize_access_token(request)
        user_info = token.get('userinfo')

        if not user_info:
            # If userinfo not included in token, fetch it using userinfo endpoint
            # Note: parse_id_token returns a dict, not a coroutine
            user_info = oauth.oidc.parse_id_token(request, token)

        # Extract key fields
        oidc_sub = user_info.get('sub')
        email = user_info.get('email')
        name = user_info.get('name') or email
        tenant_id = user_info.get('tenant_id', 'default')

        # Find or create user - use sync methods
        user = user_crud.get_by_oidc_sub(db, oidc_sub=oidc_sub)

        if not oidc_sub or not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user info from identity provider"
            )

        if not user:
            # Check if user exists with email - use sync methods
            user = user_crud.get_by_email(db, email=email)

            if user:
                # Link OIDC to existing user
                user.oidc_sub = oidc_sub
                user.oidc_issuer = settings.OIDC_ISSUER_URL
            else:
                # Create new user with OIDC information - use sync methods
                user = user_crud.create_oidc_user(
                    db,
                    email=email,
                    full_name=name,
                    oidc_sub=oidc_sub,
                    tenant_id=tenant_id,
                )

        # Generate token pair
        token_pair = create_token_pair(db, user)

        # Get the frontend callback URL from session (stored during /login)
        from_url = request.session.pop('oidc_from_url', None)

        if from_url:
            separator = '&' if '?' in from_url else '?'
            redirect_url = (
                f"{from_url}{separator}token={token_pair.access_token}"
                f"&refresh_token={token_pair.refresh_token}"
            )
        else:
            redirect_url = (
                f"/auth-callback?token={token_pair.access_token}"
                f"&refresh_token={token_pair.refresh_token}"
            )
        return RedirectResponse(
            url=redirect_url,
            status_code=status.HTTP_307_TEMPORARY_REDIRECT
        )

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("OIDC Callback error: %s", e, exc_info=True)
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Authentication failed. Please try again."}
        )


@router.get("/userinfo")
def oidc_userinfo(
        request: Request,
        db: Session = Depends(deps.get_db),
        current_user=Depends(deps.get_current_active_user)
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
