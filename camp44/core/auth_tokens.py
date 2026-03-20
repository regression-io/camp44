"""Token pair creation helper used by all login flows."""

import uuid
from typing import Optional

from sqlmodel import Session

from camp44.core.config import settings
from camp44.core.security import create_access_token
from camp44.crud import refresh_token as rt_crud
from camp44.models.token import Token
from camp44.models.user import User


def create_token_pair(
    db: Session,
    user: User,
    *,
    family_id: Optional[uuid.UUID] = None,
) -> Token:
    """
    Create a short-lived access token + rotated refresh token.

    Args:
        db: Database session.
        user: Authenticated user.
        family_id: Existing family ID when rotating; None for new sessions.

    Returns:
        Token with access_token, refresh_token, and expires_in.

    """
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tv": user.token_version,
            "tenant_id": user.tenant_id,
        }
    )

    raw_refresh, _ = rt_crud.create(
        db,
        user_id=user.id,
        token_version=user.token_version,
        family_id=family_id,
    )
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=raw_refresh,
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )
