from typing import Any, Dict, Optional

from sqlmodel import Session, select

from camp44.core.security import get_password_hash, verify_password
from camp44.models.user import User, UserCreate, UserUpdate


def get(session: Session, id: str) -> Optional[User]:
    """Get a user by id."""
    return session.get(User, id)


def get_user_by_email(session: Session, *, email: str) -> Optional[User]:
    """Get a user by email."""
    statement = select(User).where(User.email == email)
    return session.exec(statement).first()


def create_user(session: Session, *, user_in: UserCreate) -> User:
    """Create a new user."""
    db_obj = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        roles=user_in.roles,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def authenticate(
    session: Session, *, email: str, password: str
) -> Optional[User]:
    """Authenticate a user."""
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


def update_user(
    session: Session, *, db_user: User, user_in: UserUpdate
) -> User:
    """Update a user."""
    user_data = user_in.model_dump(exclude_unset=True)
    if "password" in user_data:
        hashed_password = get_password_hash(user_data["password"])
        del user_data["password"]
        user_data["hashed_password"] = hashed_password

    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.flush()
    session.refresh(db_user)
    return db_user
