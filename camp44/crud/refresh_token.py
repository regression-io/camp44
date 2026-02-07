import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlmodel import Session, select

from camp44.core.config import settings
from camp44.core.security import create_refresh_token_value, hash_refresh_token
from camp44.models.refresh_token import RefreshToken


def create(
    session: Session,
    *,
    user_id: uuid.UUID,
    token_version: int,
    family_id: Optional[uuid.UUID] = None,
) -> Tuple[str, RefreshToken]:
    """Create a new refresh token, returning (raw_token, db_obj).

    NOTE: Does NOT commit — caller is responsible for transaction boundary.
    """
    raw_token = create_refresh_token_value()
    token_hash = hash_refresh_token(raw_token)

    db_obj = RefreshToken(
        token_hash=token_hash,
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_version=token_version,
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )
    session.add(db_obj)
    session.flush()
    return raw_token, db_obj


def get_by_token(
    session: Session, *, raw_token: str
) -> Optional[RefreshToken]:
    """Look up a refresh token by its raw value (hashed for lookup)."""
    token_hash = hash_refresh_token(raw_token)
    return session.exec(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    ).first()


def revoke_family(session: Session, *, family_id: uuid.UUID) -> int:
    """Mark all tokens in a family as revoked. Returns count.

    NOTE: Does NOT commit — caller is responsible for transaction boundary.
    """
    tokens = session.exec(
        select(RefreshToken).where(
            RefreshToken.family_id == family_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    ).all()
    for t in tokens:
        t.is_revoked = True
        session.add(t)
    return len(tokens)


def revoke_user_tokens(session: Session, *, user_id: uuid.UUID) -> int:
    """Revoke all refresh tokens for a user. Returns count.

    NOTE: Does NOT commit — caller is responsible for transaction boundary.
    """
    tokens = session.exec(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.is_revoked == False,  # noqa: E712
        )
    ).all()
    for t in tokens:
        t.is_revoked = True
        session.add(t)
    return len(tokens)


def cleanup_expired(session: Session) -> int:
    """Delete expired refresh tokens. Returns count deleted."""
    now = datetime.now(timezone.utc)
    expired = session.exec(
        select(RefreshToken).where(RefreshToken.expires_at < now)
    ).all()
    for t in expired:
        session.delete(t)
    session.commit()
    return len(expired)
