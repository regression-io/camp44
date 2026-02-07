import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from camp44.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = settings.ALGORITHM


def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Create a new access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password.

    bcrypt has a 72-byte limit, so we truncate if needed.
    """
    # Truncate to 72 bytes for bcrypt compatibility
    password_bytes = plain_password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.verify(password_bytes, hashed_password)


def create_refresh_token_value() -> str:
    """Generate a cryptographically secure refresh token string."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    """Return the SHA-256 hex digest of a raw refresh token."""
    return hashlib.sha256(token.encode()).hexdigest()


def get_password_hash(password: str) -> str:
    """Hash a password.

    bcrypt has a 72-byte limit, so we truncate if needed.
    """
    # Truncate to 72 bytes for bcrypt compatibility
    password_bytes = password.encode('utf-8')[:72].decode('utf-8', errors='ignore')
    return pwd_context.hash(password_bytes)
