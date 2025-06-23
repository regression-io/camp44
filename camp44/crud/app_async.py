"""Async app CRUD operations.

This module provides async equivalents of camp44.crud.app functions.
They use SQLAlchemy async and are tenant-aware via RLS.
"""
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from camp44.models.app import App, AppCreate
from camp44.models.user import User


async def create_app_async(*, session: AsyncSession, app_in: AppCreate, owner: User) -> App:
    """Create a new app."""
    db_obj = App.model_validate(app_in, update={"owner_id": owner.id})
    session.add(db_obj)
    await session.flush()
    await session.refresh(db_obj)
    return db_obj


async def get_app_async(session: AsyncSession, id: str) -> Optional[App]:
    """Get an app by id."""
    return await session.get(App, id)


async def get_multi_by_owner_async(
    session: AsyncSession, *, owner: User, skip: int = 0, limit: int = 100
) -> List[App]:
    """Get multiple apps by owner."""
    statement = (
        select(App)
        .where(App.owner_id == owner.id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())
