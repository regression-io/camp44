from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from camp44 import crud
from camp44.api import deps, deps_async
from camp44.models.app import App
from camp44.models.entity import Entity, EntityCreate, EntityRead, EntityUpdate

router = APIRouter()


@router.post("/{entity_name}", response_model=EntityRead)
async def create_entity(
    *, 
    db: AsyncSession = Depends(deps_async.get_db), 
    app: App = Depends(deps.get_app_by_id_from_path),
    entity_name: str,
    entity_in: EntityCreate
) -> Entity:
    """Create new entity."""
    if entity_in.name != entity_name:
        raise HTTPException(status_code=400, detail=f"Entity name in path ({entity_name}) does not match name in body ({entity_in.name}).")
    entity = await crud.entity.create_entity_async(session=db, entity_in=entity_in, app=app)
    return entity


@router.post("/{entity_name}/filter", response_model=List[EntityRead])
async def filter_entities_by_name(
    *,
    db: AsyncSession = Depends(deps_async.get_db),
    app: App = Depends(deps.get_app_by_id_from_path),
    entity_name: str,
    filters: Dict[str, Any],
    skip: int = 0,
    limit: int = 100,
) -> List[Entity]:
    """Filter entities by data payload."""
    entities = await crud.entity.filter_entities_async(
        session=db, app=app, name=entity_name, filters=filters, skip=skip, limit=limit
    )
    return entities

@router.get("/{entity_name}", response_model=List[EntityRead])
async def read_entities(
    *, 
    db: AsyncSession = Depends(deps_async.get_db), 
    app: App = Depends(deps.get_app_by_id_from_path),
    entity_name: str,
    skip: int = 0,
    limit: int = 100,
) -> List[Entity]:
    """Retrieve entities."""
    entities = await crud.entity.get_multi_by_app_and_name_async(
        session=db, app=app, name=entity_name, skip=skip, limit=limit
    )
    return entities

@router.get("/{entity_name}/{id}", response_model=EntityRead)
async def read_entity(
    *, 
    db: AsyncSession = Depends(deps_async.get_db), 
    app: App = Depends(deps.get_app_by_id_from_path),
    id: str,
    entity_name: str,
) -> Entity:
    """Get entity by ID."""
    entity = await crud.entity.get_entity_async(session=db, id=id)
    if not entity or entity.app_id != app.id or entity.name != entity_name:
        raise HTTPException(status_code=404, detail="Entity not found")
    return entity

@router.patch("/{entity_name}/{id}", response_model=EntityRead)
async def update_entity(
    *, 
    db: AsyncSession = Depends(deps_async.get_db), 
    app: App = Depends(deps.get_app_by_id_from_path),
    id: str,
    entity_name: str,
    entity_in: EntityUpdate,
) -> Entity:
    """Update an entity."""
    db_entity = await crud.entity.get_entity_async(session=db, id=id)
    if not db_entity or db_entity.app_id != app.id or db_entity.name != entity_name:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity = await crud.entity.update_entity_async(session=db, db_obj=db_entity, obj_in=entity_in)
    return entity

@router.delete("/{entity_name}/{id}")
async def delete_entity(
    *, 
    db: AsyncSession = Depends(deps_async.get_db), 
    app: App = Depends(deps.get_app_by_id_from_path),
    id: str,
    entity_name: str,
) -> Any:
    """Delete an entity."""
    db_entity = await crud.entity.get_entity_async(session=db, id=id)
    if not db_entity or db_entity.app_id != app.id or db_entity.name != entity_name:
        raise HTTPException(status_code=404, detail="Entity not found")
    await crud.entity.delete_entity_async(session=db, db_obj=db_entity)
    return {"ok": True}
