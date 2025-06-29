import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from camp44 import crud
from camp44.api import deps
from camp44.models.app import App
from camp44.models.entity import Entity, EntityCreate, EntityRead, EntityUpdate

router = APIRouter()

# Set up logging
logger = logging.getLogger(__name__)


@router.post("/{entity_name}", response_model=EntityRead)
def create_entity(
        *,
        request: Request,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        entity_name: str,
        entity_in: EntityCreate
) -> Entity:
    """Create new entity."""
    logger.debug(f"CREATE ENTITY - Path: {request.url.path}")
    logger.debug(f"CREATE ENTITY - Path params: {request.path_params}")
    logger.debug(f"CREATE ENTITY - app_id: {app.id if app else 'None'}")
    logger.debug(f"CREATE ENTITY - entity_name: {entity_name}")
    logger.debug(f"CREATE ENTITY - entity_in: {entity_in}")

    if entity_in.name != entity_name:
        logger.error(f"Entity name mismatch: path={entity_name}, body={entity_in.name}")
        raise HTTPException(status_code=400, detail=f"Entity name in path ({entity_name}) does not match name in body ({entity_in.name}).")

    try:
        entity = crud.entity.create_entity(session=db, entity_in=entity_in, app=app)
        logger.debug(f"CREATE ENTITY - Created entity with ID: {entity.id}")
        return entity
    except Exception as e:
        logger.error(f"CREATE ENTITY - Exception: {e}")
        raise


@router.post("/{entity_name}/filter", response_model=List[EntityRead])
def filter_entities_by_name(
        *,
        request: Request,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        entity_name: str,
        filters: Dict[str, Any],
        skip: int = 0,
        limit: int = 100,
) -> List[Entity]:
    """Filter entities by data payload."""
    logger.debug(f"FILTER ENTITIES - Path: {request.url.path}")
    logger.debug(f"FILTER ENTITIES - Path params: {request.path_params}")
    logger.debug(f"FILTER ENTITIES - app_id: {app.id if app else 'None'}")
    logger.debug(f"FILTER ENTITIES - entity_name: {entity_name}")
    logger.debug(f"FILTER ENTITIES - filters: {filters}")

    try:
        entities = crud.entity.filter_entities(
            session=db, app=app, name=entity_name, filters=filters, skip=skip, limit=limit
        )
        logger.debug(f"FILTER ENTITIES - Found {len(entities)} entities")
        return entities
    except Exception as e:
        logger.error(f"FILTER ENTITIES - Exception: {e}")
        raise


@router.get("/{entity_name}", response_model=List[EntityRead])
def read_entities(
        *,
        request: Request,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        entity_name: str,
        skip: int = 0,
        limit: int = 100,
) -> List[Entity]:
    """Retrieve entities."""
    logger.debug(f"GET ENTITIES - Path: {request.url.path}")
    logger.debug(f"GET ENTITIES - Path params: {request.path_params}")
    logger.debug(f"GET ENTITIES - app_id: {app.id if app else 'None'}")
    logger.debug(f"GET ENTITIES - entity_name: {entity_name}")

    try:
        entities = crud.entity.get_multi_by_app_and_name(
            session=db, app=app, name=entity_name, skip=skip, limit=limit
        )
        logger.debug(f"GET ENTITIES - Found {len(entities)} entities")
        return entities
    except Exception as e:
        logger.error(f"GET ENTITIES - Exception: {e}")
        raise


@router.get("/{entity_name}/{id}", response_model=EntityRead)
def read_entity(
        *,
        request: Request,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        id: str,
        entity_name: str,
) -> Entity:
    """Retrieve an entity."""
    logger.debug(f"READ ENTITY - Path: {request.url.path}")
    logger.debug(f"READ ENTITY - Path params: {request.path_params}")
    logger.debug(f"READ ENTITY - app_id: {app.id if app else 'None'}")
    logger.debug(f"READ ENTITY - entity_name: {entity_name}")
    logger.debug(f"READ ENTITY - id: {id}")

    try:
        entity = crud.entity.get_entity(session=db, id=id)
        if not entity:
            logger.error(f"Entity {id} not found")
            raise HTTPException(status_code=404, detail=f"Entity {id} not found")
        if entity.app_id != app.id:
            logger.error(f"Entity app_id {entity.app_id} does not match app_id {app.id}")
            raise HTTPException(status_code=403, detail="Not enough permissions")
        if entity.name != entity_name:
            logger.error(f"Entity name {entity.name} does not match path entity_name {entity_name}")
            raise HTTPException(status_code=400, detail=f"Entity id {id} does not match entity name {entity_name}")
        logger.debug(f"READ ENTITY - Successfully found entity")
        return entity
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"READ ENTITY - Exception: {e}")
        raise


@router.patch("/{entity_name}/{id}", response_model=EntityRead)
def update_entity(
        *,
        request: Request,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        id: str,
        entity_name: str,
        entity_in: EntityUpdate,
) -> Entity:
    """Update an entity."""
    logger.debug(f"UPDATE ENTITY - Path: {request.url.path}")
    logger.debug(f"UPDATE ENTITY - Path params: {request.path_params}")
    logger.debug(f"UPDATE ENTITY - app_id: {app.id if app else 'None'}")
    logger.debug(f"UPDATE ENTITY - entity_name: {entity_name}")
    logger.debug(f"UPDATE ENTITY - id: {id}")
    logger.debug(f"UPDATE ENTITY - entity_in: {entity_in}")

    db_entity = crud.entity.get_entity(session=db, id=id)
    if not db_entity or db_entity.app_id != app.id or db_entity.name != entity_name:
        raise HTTPException(status_code=404, detail="Entity not found")
    entity = crud.entity.update_entity(session=db, db_obj=db_entity, obj_in=entity_in)
    return entity


@router.delete("/{entity_name}/{id}")
def delete_entity(
        *,
        request: Request,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        id: str,
        entity_name: str,
) -> Any:
    """Delete an entity."""
    logger.debug(f"DELETE ENTITY - Path: {request.url.path}")
    logger.debug(f"DELETE ENTITY - Path params: {request.path_params}")
    logger.debug(f"DELETE ENTITY - app_id: {app.id if app else 'None'}")
    logger.debug(f"DELETE ENTITY - entity_name: {entity_name}")
    logger.debug(f"DELETE ENTITY - id: {id}")

    try:
        entity = crud.entity.get_entity(session=db, id=id)
        if not entity:
            logger.error(f"Entity {id} not found")
            raise HTTPException(status_code=404, detail=f"Entity {id} not found")
        if entity.app_id != app.id:
            logger.error(f"Entity app_id {entity.app_id} does not match app_id {app.id}")
            raise HTTPException(status_code=403, detail="Not enough permissions")
        if entity.name != entity_name:
            logger.error(f"Entity name {entity.name} does not match path entity_name {entity_name}")
            raise HTTPException(status_code=400, detail=f"Entity id {id} does not match entity name {entity_name}")
        crud.entity.delete_entity(session=db, db_obj=entity)
        logger.debug(f"DELETE ENTITY - Successfully deleted entity")
        return {"ok": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"DELETE ENTITY - Exception: {e}")
        raise
