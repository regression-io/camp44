"""
Middleware to extract tenant_id from OIDC tokens and set it in request.state.
"""
from typing import Callable

from fastapi import Request, Response
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from camp44.core.config import settings
from camp44.core.oauth import OIDCTokenValidator


class OIDCTenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that extracts tenant_id from OIDC tokens and sets it in request.state.
    This works alongside the regular TenantMiddleware to provide tenant context
    for both JWT and OIDC authentication flows.
    """
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip middleware if OAuth is not enabled
        if not settings.OAUTH_ENABLED:
            return await call_next(request)
            
        # Extract the Bearer token from the Authorization header
        authorization: str = request.headers.get("Authorization", "")
        scheme, token = get_authorization_scheme_param(authorization)
        
        # Only process Bearer tokens
        if scheme.lower() == "bearer" and token:
            # Validate the token and extract claims
            claims = await OIDCTokenValidator.validate_token(token)
            
            if claims and settings.OIDC_TENANT_CLAIM in claims:
                # Extract tenant_id from the specified claim
                tenant_id = claims.get(settings.OIDC_TENANT_CLAIM)
                
                # Store tenant_id in request.state
                # This will be used by the SQL connection hooks to set app.tenant_id
                if tenant_id:
                    request.state.tenant_id = tenant_id
        
        return await call_next(request)
