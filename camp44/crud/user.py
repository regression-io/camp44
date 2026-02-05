from typing import Optional

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


# Alias for OIDC callback compatibility
def get_by_email(session: Session, *, email: str) -> Optional[User]:
    """Get a user by email (alias for get_user_by_email)."""
    return get_user_by_email(session, email=email)


def get_by_oidc_sub(session: Session, *, oidc_sub: str) -> Optional[User]:
    """Get a user by OIDC subject identifier."""
    statement = select(User).where(User.oidc_sub == oidc_sub)
    return session.exec(statement).first()


def get_by_stripe_customer_id(session: Session, *, customer_id: str) -> Optional[User]:
    """Get a user by Stripe customer ID."""
    statement = select(User).where(User.stripe_customer_id == customer_id)
    return session.exec(statement).first()


def get_by_password_reset_token(session: Session, *, token: str) -> Optional[User]:
    """Get a user by password reset token."""
    statement = select(User).where(User.password_reset_token == token)
    return session.exec(statement).first()


def create_oidc_user(
    session: Session,
    *,
    email: str,
    full_name: str,
    oidc_sub: str,
    tenant_id: str = "default",
) -> User:
    """Create a new user from OIDC authentication."""
    db_obj = User(
        email=email,
        display_name=full_name,
        oidc_sub=oidc_sub,
        tenant_id=tenant_id,
        oidc_email_verified=True,
        hashed_password=None,  # OIDC users don't have passwords
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


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
    if not db_user.hashed_password:
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
    session.commit()
    session.refresh(db_user)
    return db_user


def update(session: Session, *, db_obj: User, obj_in: dict) -> User:
    """Update a user from a dictionary (used by passkey flows)."""
    db_obj.sqlmodel_update(obj_in)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def get_users_with_passkey(session: Session, *, credential_id: str) -> list[User]:
    """Find users that have a specific passkey credential ID registered."""
    all_users = session.exec(select(User)).all()
    matched = []
    for u in all_users:
        if u.passkey_credentials:
            for cred in u.passkey_credentials:
                if cred.get("id") == credential_id:
                    matched.append(u)
                    break
    return matched
