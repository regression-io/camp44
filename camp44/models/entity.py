import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy import Column
from sqlalchemy import JSON
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .app import App


class Entity(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    data: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    app_id: uuid.UUID = Field(foreign_key="app.id")
    app: "App" = Relationship(back_populates="entities")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, sa_column_kwargs={"onupdate": datetime.utcnow}
    )


class EntityCreate(SQLModel):
    name: str
    data: Dict[str, Any]


class EntityRead(SQLModel):
    id: uuid.UUID
    name: str
    data: Dict[str, Any]
    app_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class EntityUpdate(SQLModel):
    data: Optional[Dict[str, Any]] = None
