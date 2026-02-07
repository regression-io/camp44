"""Middleware that returns 410 Gone for routes whose Camp44 feature is disabled.

Host applications (e.g. ScaleMate) can disable Camp44 route groups they don't
use by setting CAMP44_DISABLE_{FEATURE}=true in environment variables.
"""
from __future__ import annotations

import logging
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from camp44.core.config import settings

logger = logging.getLogger(__name__)

# Map: flag attribute name → list of route path prefixes to block
_FLAG_ROUTES: dict[str, list[str]] = {
    "CAMP44_DISABLE_FUNCTIONS": ["/functions", "/api/functions"],
    "CAMP44_DISABLE_METERING": ["/metering", "/api/metering"],
    "CAMP44_DISABLE_DEMO_BOOKING": ["/demo", "/api/demo"],
    "CAMP44_DISABLE_BASE44_PROXY": ["/base44", "/api/base44"],
    "CAMP44_DISABLE_BULK": ["/apps/{app_id}/bulk", "/api/apps/{app_id}/bulk"],
    "CAMP44_DISABLE_ADMIN": ["/admin", "/api/admin"],
    "CAMP44_DISABLE_PASSKEY": ["/auth/passkey"],
    "CAMP44_DISABLE_OIDC": ["/auth/oidc"],
    "CAMP44_DISABLE_INTEGRATIONS": [
        "/apps/{app_id}/integrations",
        "/api/apps/{app_id}/integrations",
    ],
    "CAMP44_DISABLE_ENTITIES": [
        "/apps/{app_id}/entities",
        "/api/apps/{app_id}/entities",
    ],
    "CAMP44_DISABLE_PUBLIC": ["/api/apps/public"],
    "CAMP44_DISABLE_APPS": ["/apps", "/api/apps"],
    "CAMP44_DISABLE_STRIPE": ["/stripe", "/api/stripe"],
}

def _build_blocked_prefixes() -> list[str]:
    """Build the list of blocked route prefixes from settings."""
    blocked: list[str] = []
    for flag, prefixes in _FLAG_ROUTES.items():
        if getattr(settings, flag, False):
            blocked.extend(prefixes)
            logger.info("Feature flag %s=True — blocking routes: %s", flag, prefixes)
    return blocked


def _matches_blocked(path: str, blocked: list[str]) -> bool:
    """Check if a request path matches any blocked prefix.

    Handles {app_id} wildcards in prefix patterns by matching the
    corresponding path segment against any value.
    """
    for prefix in blocked:
        if "{app_id}" in prefix:
            # Split pattern and path into segments for wildcard matching
            pattern_parts = prefix.split("/")
            path_parts = path.split("/")
            if len(path_parts) >= len(pattern_parts):
                match = True
                for i, pp in enumerate(pattern_parts):
                    if pp == "{app_id}":
                        continue
                    if pp != path_parts[i]:
                        match = False
                        break
                if match:
                    return True
        elif path.startswith(prefix):
            return True
    return False


class FeatureFlagMiddleware(BaseHTTPMiddleware):
    """Return 410 Gone for disabled Camp44 features."""

    def __init__(self, app: Any, **kwargs: Any) -> None:
        super().__init__(app, **kwargs)
        self._blocked = _build_blocked_prefixes()

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        if self._blocked and _matches_blocked(request.url.path, self._blocked):
            return JSONResponse(
                status_code=410,
                content={"detail": "This feature is disabled."},
            )
        return await call_next(request)
