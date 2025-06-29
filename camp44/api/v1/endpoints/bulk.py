from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from camp44 import crud
from camp44.api import deps
from camp44.models.app import App
from camp44.models.bulk import BulkRequest, BulkResponse
from camp44.models.entity import EntityCreate, EntityUpdate

router = APIRouter()


@router.post("/", response_model=BulkResponse)
def bulk_operations(
        *,
        db: Session = Depends(deps.get_db),
        app: App = Depends(deps.get_app_by_id_from_path),
        request: BulkRequest
) -> Any:
    """Perform bulk operations on entities."""
    results = []
    for op in request.operations:
        if op.op == "create":
            entity_in = EntityCreate(name=op.entity_name, data=op.data)
            entity = crud.entity.create_entity(session=db, entity_in=entity_in, app=app)
            results.append({"id": entity.id, "op": "create", "status": "success"})
        elif op.op == "update":
            db_entity = crud.entity.get_entity(session=db, id=op.id)
            if not db_entity or db_entity.app_id != app.id or db_entity.name != op.entity_name:
                results.append({"id": op.id, "op": "update", "status": "not_found"})
                continue
            entity_in = EntityUpdate(data=op.data)
            crud.entity.update_entity(session=db, db_obj=db_entity, obj_in=entity_in)
            results.append({"id": op.id, "op": "update", "status": "success"})
        elif op.op == "delete":
            db_entity = crud.entity.get_entity(session=db, id=op.id)
            if not db_entity or db_entity.app_id != app.id or db_entity.name != op.entity_name:
                results.append({"id": op.id, "op": "delete", "status": "not_found"})
                continue
            crud.entity.delete_entity(session=db, db_obj=db_entity)
            results.append({"id": op.id, "op": "delete", "status": "success"})

    return BulkResponse(results=results)
