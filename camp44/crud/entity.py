import re
import uuid
from typing import Any, Dict, List, Optional, Union

from sqlmodel import Session, select

from camp44.models.app import App
from camp44.models.entity import Entity, EntityCreate, EntityUpdate

# Only allow safe characters in JSON filter keys (prevents SQL injection)
_SAFE_KEY_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def create_entity(*, session: Session, entity_in: EntityCreate, app: App) -> Entity:
    """Create a new entity."""
    db_obj = Entity.model_validate(entity_in, update={"app_id": app.id})
    session.add(db_obj)
    session.commit()
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
    for idx, (key, value) in enumerate(filters.items()):
        # Validate key to prevent SQL injection (keys are interpolated into SQL)
        if not _SAFE_KEY_RE.match(key):
            continue
        param_name = f"fval_{idx}"
        if isinstance(value, str):
            statement = statement.where(
                text(f"data->>'{key}' = :{param_name}").bindparams(**{param_name: value})
            )
        elif isinstance(value, (int, float, bool)):
            statement = statement.where(
                text(f"(data->>'{key}')::text = :{param_name}").bindparams(**{param_name: str(value)})
            )
        else:
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
    session.commit()
    session.refresh(db_obj)
    return db_obj


def delete_entity(session: Session, *, db_obj: Entity) -> None:
    """Delete an entity."""
    session.delete(db_obj)
    session.commit()
