import hashlib
from typing import Optional

from sqlmodel import Session, select

from camp44.core.security import get_password_hash, verify_password
from camp44.models.user import User, UserCreate, UserUpdate


def _is_admin_domain(email: str) -> bool:
    """Check if email belongs to an auto-admin domain."""
    from camp44.core.config import settings

    domain = email.rsplit("@", 1)[-1].lower()
    admin_domains = [
        d.strip().lower() for d in settings.ADMIN_EMAIL_DOMAINS.split(",") if d.strip()
    ]
    return domain in admin_domains


def _ensure_admin_role(user: User, session: Session) -> None:
    """
    Add admin role if user's email domain is in ADMIN_EMAIL_DOMAINS.

    Skips users whose admin privileges were explicitly removed via the
    remove-admin endpoint (``user.admin_removed is True``).
    """
    if user.admin_removed:
        return
    # Only auto-promote if email ownership is reasonably assured:
    # - OIDC users must have email verified by the IdP
    # - Password users are trusted (they registered through our flow)
    if not (user.hashed_password or user.oidc_email_verified):
        return
    if _is_admin_domain(user.email) and "admin" not in (user.roles or []):
        user.roles = (user.roles or []) + ["admin"]
        session.add(user)
        session.commit()
        session.refresh(user)


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
    hashed = hashlib.sha256(token.encode()).hexdigest()
    statement = select(User).where(User.password_reset_token == hashed)
    return session.exec(statement).first()


def create_oidc_user(
    session: Session,
    *,
    email: str,
    full_name: str,
    oidc_sub: str,
    tenant_id: str | None = None,
) -> User:
    """Create a new user from OIDC authentication."""
    # OIDC users are IdP-verified, so auto-admin is safe here
    roles = ["admin"] if _is_admin_domain(email) else []
    db_obj = User(
        email=email,
        display_name=full_name,
        oidc_sub=oidc_sub,
        tenant_id=tenant_id,
        oidc_email_verified=True,
        hashed_password=None,  # OIDC users don't have passwords
        roles=roles,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def create_user(session: Session, *, user_in: UserCreate) -> User:
    """Create a new user."""
    # Do NOT auto-promote at signup — email is unverified at this point.
    # _ensure_admin_role will promote on first login once email ownership
    # is established (password users pass the hashed_password check).
    roles = list(user_in.roles)
    db_obj = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        roles=roles,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def authenticate(session: Session, *, email: str, password: str) -> Optional[User]:
    """Authenticate a user."""
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    if not db_user.hashed_password:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    # Auto-promote admin-domain users on login
    _ensure_admin_role(db_user, session)
    return db_user


def update_user(session: Session, *, db_user: User, user_in: UserUpdate) -> User:
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
    """
    Find users that have a specific passkey credential ID registered.

    Uses PostgreSQL JSONB containment query instead of scanning all users.
    Falls back to Python scan for non-PostgreSQL backends (e.g., SQLite in tests).
    """
    import json

    # Try PostgreSQL JSONB containment operator
    try:
        cred_json = json.dumps([{"id": credential_id}])
        statement = select(User).where(
            User.passkey_credentials.op("@>")(cred_json)  # type: ignore[union-attr]
        )
        return list(session.exec(statement).all())
    except Exception:
        # Fallback for SQLite (tests) — scan in Python
        all_users = session.exec(select(User)).all()
        matched = []
        for u in all_users:
            if u.passkey_credentials:
                for cred in u.passkey_credentials:
                    if cred.get("id") == credential_id:
                        matched.append(u)
                        break
        return matched
