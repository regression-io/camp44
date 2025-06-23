from __future__ import annotations

"""Async equivalents of dependency helpers.

These will gradually replace the sync `api.deps` helpers as the codebase moves
onto SQLAlchemy asyncio and tenant-aware sessions.
"""

import uuid
from typing import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from camp44 import crud
from camp44.core.config import settings
from db.engine import get_async_db
from camp44.models.token import TokenPayload
from camp44.models.user import User
from camp44.models.app import App

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


async def get_db(request: Request) -> AsyncGenerator[AsyncSession, None]:
    """Yield an `AsyncSession` with tenant_id taken from request state."""
    tenant_id: str | None = getattr(request.state, "tenant_id", None)
    async with get_async_db(tenant_id=tenant_id) as session:
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """Get the current user from a token asynchronously."""
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        token_data = TokenPayload(**payload)
    except (jwt.JWTError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        ) from e
    
    user = await crud.user_async.get(db, id=uuid.UUID(token_data.sub))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Check if current user is active and return it."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


async def get_app_by_id_from_path(
    app_id: str,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> App:
    """Get an app by its ID from the path and verify the current user has access."""
    app = await crud.app_async.get(session, id=app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return app
