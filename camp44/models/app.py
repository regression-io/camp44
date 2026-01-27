import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import JSON
from sqlmodel import Column, Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User
    from .entity import Entity


class AppBase(SQLModel):
    name: str
    description: Optional[str] = None


class App(AppBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    stripe_price_id: Optional[str] = Field(default=None)
    requires_auth: bool = Field(default=True)  # Default to requiring auth
    public_settings: Dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: "User" = Relationship(back_populates="apps")
    entities: List["Entity"] = Relationship(back_populates="app", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class AppCreate(AppBase):
    requires_auth: bool = True
    public_settings: Dict[str, Any] = {}


class AppRead(AppBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    stripe_price_id: Optional[str] = None
    requires_auth: bool = True
    public_settings: Dict[str, Any] = {}


class AppPublicSettings(SQLModel):
    """Public settings response - no sensitive data."""
    id: uuid.UUID
    name: str
    requires_auth: bool
    public_settings: Dict[str, Any]
