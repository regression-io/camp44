from __future__ import annotations

"""Middleware that extracts tenant_id from a verified token and stores it on
`request.state.tenant_id` so the DB layer can set the Postgres session
variable used by RLS policies.

This first cut reuses the existing JWT validation logic from `api.deps`. In a
future slice we will swap to full OIDC / Passkeys flows.
"""

from typing import Callable, Any

from fastapi import Request
from jose import jwt, JWTError
from starlette.middleware.base import BaseHTTPMiddleware

from camp44.core.config import settings


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """Extract tenant_id from JWT and store it in request state."""
        # Default: anonymous tenant (NULL) → RLS rejects access.
        tenant_id: str | None = None

        auth_header: str | None = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
                tenant_id = payload.get("tenant_id")  # expected claim
            except JWTError:
                # Ignore invalid tokens; downstream auth deps will 401.
                pass

        request.state.tenant_id = tenant_id
        response = await call_next(request)
        return response
