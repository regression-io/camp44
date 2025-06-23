"""
OAuth/OIDC client and utilities.
"""
from typing import Dict, Optional

from authlib.integrations.starlette_client import OAuth
from authlib.jose import JsonWebKey, JsonWebToken, jwt
from authlib.jose.errors import JoseError
import httpx
import json

from camp44.core.config import settings

# Initialize OAuth client
oauth = OAuth()

if settings.OAUTH_ENABLED and settings.OIDC_CLIENT_ID and settings.OIDC_CLIENT_SECRET:
    # Register OIDC provider
    oauth.register(
        name='oidc',
        client_id=settings.OIDC_CLIENT_ID,
        client_secret=settings.OIDC_CLIENT_SECRET,
        server_metadata_url=f"{settings.OIDC_ISSUER_URL}/.well-known/openid-configuration" if settings.OIDC_ISSUER_URL else None,
        client_kwargs={
            'scope': ' '.join(settings.OIDC_SCOPES)
        },
    )


class OIDCTokenValidator:
    """Validates OIDC tokens and extracts claims."""
    
    _jwks = None
    
    @classmethod
    async def get_jwks(cls) -> Dict:
        """Fetch and cache JSON Web Key Set from the IdP."""
        if cls._jwks is None and settings.OIDC_JWKS_URI:
            async with httpx.AsyncClient() as client:
                response = await client.get(settings.OIDC_JWKS_URI)
                cls._jwks = response.json()
        return cls._jwks or {}
    
    @classmethod
    async def validate_token(cls, token: str) -> Optional[Dict]:
        """
        Validate an OIDC token and extract its claims.
        
        Args:
            token: The OIDC token to validate
            
        Returns:
            Dict of claims if valid, None if invalid
        """
        if not settings.OAUTH_ENABLED:
            return None
            
        try:
            # Get the JSON Web Key Set
            jwks = await cls.get_jwks()
            
            # Parse the token header
            jwt_obj = JsonWebToken(['RS256'])
            claims = jwt_obj.decode(
                token,
                JsonWebKey.import_key_set(jwks),
                claims_options={
                    'iss': {'essential': True, 'value': settings.OIDC_ISSUER_URL},
                    'aud': {'essential': True, 'value': settings.OIDC_CLIENT_ID},
                }
            )
            claims.validate()
            return claims
            
        except (JoseError, ValueError) as e:
            # Invalid token
            print(f"Token validation error: {str(e)}")
            return None
