import uuid
from typing import Any, Dict, List, Literal, Union

from pydantic import BaseModel, Field


class BulkCreate(BaseModel):
    op: Literal["create"]
    entity_name: str
    data: Dict[str, Any]


class BulkUpdate(BaseModel):
    op: Literal["update"]
    entity_name: str
    id: uuid.UUID
    data: Dict[str, Any]


class BulkDelete(BaseModel):
    op: Literal["delete"]
    entity_name: str
    id: uuid.UUID


BulkOperation = Union[BulkCreate, BulkUpdate, BulkDelete]


class BulkRequest(BaseModel):
    operations: List[BulkOperation] = Field(..., max_items=100)


class BulkResponse(BaseModel):
    results: List[Dict[str, Any]]
