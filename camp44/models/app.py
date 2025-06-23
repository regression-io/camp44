import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from .user import User
    from .entity import Entity


class AppBase(SQLModel):
    name: str
    description: Optional[str] = None


class App(AppBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    stripe_price_id: Optional[str] = Field(default=None)
    owner_id: uuid.UUID = Field(foreign_key="user.id")
    owner: "User" = Relationship(back_populates="apps")
    entities: List["Entity"] = Relationship(back_populates="app", sa_relationship_kwargs={"cascade": "all, delete-orphan"})


class AppCreate(AppBase):
    pass


class AppRead(AppBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    stripe_price_id: Optional[str] = None
