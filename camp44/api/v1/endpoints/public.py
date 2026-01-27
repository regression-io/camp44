"""Public endpoints that don't require authentication.

These endpoints are used by frontends to check app configuration
before the user is authenticated.
"""
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from jose import jwt
from pydantic import BaseModel
from sqlmodel import Session

from camp44 import crud
from camp44.api import deps
from camp44.core.config import settings
from camp44.models.app import AppPublicSettings

router = APIRouter()


class AuthRequiredError(BaseModel):
    """Error response when authentication is required."""
    detail: str
    extra_data: dict


def get_optional_user_id(
    authorization: Optional[str] = Header(None),
) -> Optional[uuid.UUID]:
    """Extract user ID from token if present, without requiring auth."""
    if not authorization:
        return None

    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None

    token = parts[1]
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return uuid.UUID(payload.get("sub"))
    except Exception:
        return None


@router.get(
    "/prod/public-settings/by-id/{app_id}",
    response_model=AppPublicSettings,
    responses={
        403: {
            "description": "Authentication required or user not registered",
            "model": AuthRequiredError,
        },
        404: {"description": "App not found"},
    },
)
def get_app_public_settings(
    app_id: uuid.UUID,
    db: Session = Depends(deps.get_db),
    user_id: Optional[uuid.UUID] = Depends(get_optional_user_id),
):
    """Get public settings for an app.

    This endpoint is public and used by frontends to determine:
    - If the app exists
    - If authentication is required
    - Public configuration settings

    Returns:
        200: App public settings
        403: Auth required (extra_data.reason = "auth_required")
        403: User not registered (extra_data.reason = "user_not_registered")
        404: App not found
    """
    app = crud.app.get_app(db, id=app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")

    # If app requires auth and user is not authenticated
    if app.requires_auth and user_id is None:
        # Return 403 with extra_data.reason for frontend to handle
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "Authentication required",
                "extra_data": {"reason": "auth_required"},
            },
        )

    # If user is authenticated, verify they exist and are active
    if user_id is not None:
        user = crud.user.get(db, id=user_id)
        if not user:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "User not registered for this app",
                    "extra_data": {"reason": "user_not_registered"},
                },
            )
        if not user.is_active:
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "User account is inactive",
                    "extra_data": {"reason": "user_inactive"},
                },
            )

    return AppPublicSettings(
        id=app.id,
        name=app.name,
        requires_auth=app.requires_auth,
        public_settings=app.public_settings or {},
    )
