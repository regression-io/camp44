"""Async entity CRUD operations.

This module provides async equivalents of camp44.crud.entity functions.
They use SQLAlchemy async and are tenant-aware via RLS.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from camp44.models.app import App
from camp44.models.entity import Entity, EntityCreate, EntityUpdate


async def create_entity_async(*, session: AsyncSession, entity_in: EntityCreate, app: App) -> Entity:
    """Create a new entity."""
    db_obj = Entity.model_validate(entity_in, update={"app_id": app.id})
    session.add(db_obj)
    await session.flush()
    await session.refresh(db_obj)
    return db_obj


async def get_entity_async(session: AsyncSession, id: str) -> Optional[Entity]:
    """Get an entity by id."""
    return await session.get(Entity, id)


async def get_multi_by_app_and_name_async(
    session: AsyncSession, *, app: App, name: str, skip: int = 0, limit: int = 100
) -> List[Entity]:
    """Get multiple entities by app and name."""
    statement = (
        select(Entity)
        .where(Entity.app_id == app.id, Entity.name == name)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(statement)
    return list(result.scalars().all())


async def filter_entities_async(
    session: AsyncSession, *, app: App, name: str, filters: Dict[str, Any], skip: int = 0, limit: int = 100
) -> List[Entity]:
    """Filter entities by app, name, and data filters."""
    statement = (
        select(Entity)
        .where(Entity.app_id == app.id, Entity.name == name)
    )
    for key, value in filters.items():
        statement = statement.where(Entity.data[key].astext == str(value))

    statement = statement.offset(skip).limit(limit)
    result = await session.execute(statement)
    return list(result.scalars().all())


async def update_entity_async(
    session: AsyncSession, *, db_obj: Entity, obj_in: EntityUpdate
) -> Entity:
    """Update an entity."""
    update_data = obj_in.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_data)
    session.add(db_obj)
    await session.flush()
    await session.refresh(db_obj)
    return db_obj


async def delete_entity_async(session: AsyncSession, *, db_obj: Entity) -> None:
    """Delete an entity."""
    await session.delete(db_obj)
    await session.flush()
