import uuid
from typing import List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select

from camp44.models.app import App, AppCreate
from camp44.models.user import User


def create_app(*, session: Session, app_in: AppCreate, owner: User) -> App:
    """Create a new app."""
    db_obj = App.model_validate(app_in, update={"owner_id": owner.id})
    session.add(db_obj)
    session.flush()
    session.refresh(db_obj)
    return db_obj


def get_app(session: Session, id: Union[uuid.UUID, str]) -> Optional[App]:
    """Get an app by id."""
    if isinstance(id, str):
        id = uuid.UUID(id)
    return session.get(App, id)


def get_multi_by_owner(
        session: Session, *, owner: User, skip: int = 0, limit: int = 100
) -> List[App]:
    """Get multiple apps by owner."""
    statement = (
        select(App)
        .where(App.owner_id == owner.id)
        .offset(skip)
        .limit(limit)
    )
    return session.exec(statement).all()


async def create_app_async(*, session: AsyncSession, app_in: AppCreate, owner: User) -> App:
    """Create a new app asynchronously."""
    db_obj = App.model_validate(app_in, update={"owner_id": owner.id})
    session.add(db_obj)
    await session.flush()
    await session.refresh(db_obj)
    return db_obj


async def get_app_async(session: AsyncSession, id: Union[uuid.UUID, str]) -> Optional[App]:
    """Get an app by id asynchronously."""
    if isinstance(id, str):
        id = uuid.UUID(id)
    return await session.get(App, id)


async def get_multi_by_owner_async(
        session: AsyncSession, *, owner: User, skip: int = 0, limit: int = 100
) -> List[App]:
    """Get multiple apps by owner asynchronously."""
    statement = (
        select(App)
        .where(App.owner_id == owner.id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(statement)
    return result.scalars().all()
