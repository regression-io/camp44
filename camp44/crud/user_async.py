"""Async user CRUD operations.

This module provides async equivalents of camp44.crud.user functions.
They use SQLAlchemy async and are tenant-aware via RLS.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from camp44.core.security import get_password_hash, verify_password
from camp44.models.user import User, UserCreate, UserUpdate


async def get_async(session: AsyncSession, id: str) -> Optional[User]:
    """Get a user by id."""
    return await session.get(User, id)


async def get(session: AsyncSession, id: str) -> Optional[User]:
    """Alias for get_async for compatibility with sync version."""
    return await get_async(session, id)


async def get_user_by_email_async(session: AsyncSession, *, email: str) -> Optional[User]:
    """Get a user by email."""
    statement = select(User).where(User.email == email)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def get_by_email(session: AsyncSession, *, email: str) -> Optional[User]:
    """Alias for get_user_by_email_async for compatibility with sync version."""
    return await get_user_by_email_async(session=session, email=email)


async def get_by_oidc_sub(session: AsyncSession, *, oidc_sub: str) -> Optional[User]:
    """Get a user by OIDC subject identifier."""
    statement = select(User).where(User.oidc_sub == oidc_sub)
    result = await session.execute(statement)
    return result.scalar_one_or_none()


async def create_user_async(session: AsyncSession, *, user_in: UserCreate) -> User:
    """Create a new user."""
    db_obj = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        display_name=user_in.display_name,
        roles=user_in.roles,
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def authenticate_async(
    session: AsyncSession, *, email: str, password: str
) -> Optional[User]:
    """Authenticate a user."""
    db_user = await get_user_by_email_async(session=session, email=email)
    if not db_user:
        return None
    if not verify_password(password, db_user.hashed_password):
        return None
    return db_user


async def update_user_async(
    session: AsyncSession, *, db_user: User, user_in: UserUpdate
) -> User:
    """Update a user."""
    user_data = user_in.model_dump(exclude_unset=True)
    if "password" in user_data:
        hashed_password = get_password_hash(user_data["password"])
        del user_data["password"]
        user_data["hashed_password"] = hashed_password

    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    await session.flush()
    await session.refresh(db_user)
    return db_user


async def update(session: AsyncSession, *, db_obj: User, obj_in: Dict[str, Any]) -> User:
    """Update a user with dictionary data."""
    update_data = obj_in.copy()
    if "password" in update_data:
        hashed_password = get_password_hash(update_data["password"])
        del update_data["password"]
        update_data["hashed_password"] = hashed_password

    db_obj.sqlmodel_update(update_data)
    session.add(db_obj)
    await session.flush()
    await session.refresh(db_obj)
    return db_obj


async def create_oidc_user(
    session: AsyncSession, 
    *,
    email: str,
    display_name: Optional[str] = None,
    oidc_sub: str,
    oidc_issuer: str,
    oidc_email_verified: bool = False,
    tenant_id: Optional[str] = None,
    roles: List[str] = None
) -> User:
    """Create a new user via OIDC."""
    if roles is None:
        roles = ["user"]
        
    db_obj = User(
        email=email,
        display_name=display_name or email,
        oidc_sub=oidc_sub,
        oidc_issuer=oidc_issuer,
        oidc_email_verified=oidc_email_verified,
        tenant_id=tenant_id,
        roles=roles,
    )
    session.add(db_obj)
    await session.commit()
    await session.refresh(db_obj)
    return db_obj


async def get_users_with_passkey(session: AsyncSession, *, credential_id: str) -> List[User]:
    """Get users who have the given passkey credential."""
    # This can't be directly queried with SQLModel, so we need a workaround
    # We'll fetch all users and filter in Python
    statement = select(User)
    result = await session.execute(statement)
    users = result.scalars().all()
    
    # Filter users who have the specified credential
    matching_users = []
    for user in users:
        for cred in user.passkey_credentials:
            if cred.get("id") == credential_id:
                matching_users.append(user)
                break
                
    return matching_users
