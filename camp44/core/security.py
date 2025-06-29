from datetime import datetime, timedelta, timezone

from jose import jwt
from passlib.context import CryptContext

from camp44.core.config import settings

# Update to use a combination of bcrypt and sha256_crypt for better compatibility
# bcrypt alone is having issues with newer versions of the library
pwd_context = CryptContext(schemes=["bcrypt", "sha256_crypt"], deprecated="auto")

ALGORITHM = "HS256"


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
        to_encode, settings.JWT_SECRET_KEY, algorithm=ALGORITHM
    )
    return encoded_jwt


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain password against a hashed password."""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password."""
    # Use sha256_crypt by default which is more reliable across environments
    return pwd_context.hash(password)
