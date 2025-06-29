import uuid
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from pydantic import ValidationError
from sqlmodel import Session

from camp44 import crud
from camp44.core.config import settings
from camp44.db.session import engine
from camp44.models.app import App
from camp44.models.token import TokenPayload
from camp44.models.user import User

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login"
)


def get_db() -> Generator[Session, None, None]:
    """Get a database session."""
    with Session(engine) as session:
        yield session


def get_current_user(
        db: Session = Depends(get_db), token: str = Depends(reusable_oauth2)
) -> User:
    """Get the current user from a token."""
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
    user = crud.user.get(db, id=uuid.UUID(token_data.sub))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def get_current_active_user(
        current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_app_by_id_from_path(
        app_id: str,
        session: Session = Depends(get_db),
        current_user: User = Depends(get_current_active_user),
) -> App:
    """Get an app by its ID from the path and verify the current user has access."""
    app = crud.app.get_app(session, id=app_id)
    if not app:
        raise HTTPException(status_code=404, detail="App not found")
    if app.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return app
