import uuid
from typing import Any, Dict, List, Optional, Union

from sqlmodel import Session, select

from camp44.models.app import App
from camp44.models.entity import Entity, EntityCreate, EntityUpdate


def create_entity(*, session: Session, entity_in: EntityCreate, app: App) -> Entity:
    """Create a new entity."""
    db_obj = Entity.model_validate(entity_in, update={"app_id": app.id})
    session.add(db_obj)
    session.flush()
    session.refresh(db_obj)
    return db_obj


def get_entity(session: Session, id: Union[uuid.UUID, str]) -> Optional[Entity]:
    """Get an entity by id."""
    if isinstance(id, str):
        id = uuid.UUID(id)
    return session.get(Entity, id)


def get_multi_by_app_and_name(
        session: Session, *, app: App, name: str, skip: int = 0, limit: int = 100
) -> List[Entity]:
    """Get multiple entities by app and name."""
    statement = (
        select(Entity)
        .where(Entity.app_id == app.id, Entity.name == name)
        .offset(skip)
        .limit(limit)
    )
    return session.exec(statement).all()


def filter_entities(
        session: Session, *, app: App, name: str, filters: Dict[str, Any], skip: int = 0, limit: int = 100
) -> List[Entity]:
    """Filter entities by app, name, and data filters."""
    from sqlalchemy import text
    
    # Start with base query
    statement = (
        select(Entity)
        .where(Entity.app_id == app.id, Entity.name == name)
    )
    
    # Apply JSON path filters using SQLAlchemy's text() for PostgreSQL
    for key, value in filters.items():
        if isinstance(value, str):
            # For string values, use -> operator and cast the result to text
            statement = statement.where(
                text(f"data->>'{key}' = :value").bindparams(value=value)
            )
        elif isinstance(value, (int, float, bool)):
            # For numeric/boolean values, handle appropriately
            statement = statement.where(
                text(f"(data->>'{key}')::text = :value").bindparams(value=str(value))
            )
        else:
            # Skip complex objects
            continue

    statement = statement.offset(skip).limit(limit)
    return session.exec(statement).all()


def update_entity(
        session: Session, *, db_obj: Entity, obj_in: EntityUpdate
) -> Entity:
    """Update an entity."""
    update_data = obj_in.model_dump(exclude_unset=True)
    db_obj.sqlmodel_update(update_data)
    session.add(db_obj)
    session.flush()
    session.refresh(db_obj)
    return db_obj


def delete_entity(session: Session, *, db_obj: Entity) -> None:
    """Delete an entity."""
    session.delete(db_obj)
    session.flush()
