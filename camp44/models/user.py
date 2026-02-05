import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from sqlalchemy import Column
from sqlalchemy import JSON
from sqlmodel import Field, Relationship, SQLModel


# Properties to receive via API on creation
class UserCreate(SQLModel):
    email: str
    password: str
    display_name: str | None = None
    roles: List[str] = []


# Properties to return via API, id is required
class UserRead(SQLModel):
    id: uuid.UUID
    email: str
    display_name: str | None = None
    is_active: bool
    roles: list[str]
    created_at: datetime
    updated_at: datetime
    stripe_customer_id: Optional[str] = None
    oidc_sub: Optional[str] = None
    has_passkeys: bool = False


# Properties to receive via API on update
class UserUpdate(SQLModel):
    email: str | None = None
    password: str | None = None
    display_name: str | None = None


if TYPE_CHECKING:
    from .app import App


class User(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    email: str = Field(unique=True, index=True)
    display_name: Optional[str] = None
    hashed_password: Optional[str] = None  # Can be null for OIDC-only users
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
    password_reset_token: Optional[str] = Field(default=None, index=True)
    password_reset_expires: Optional[datetime] = Field(default=None)
    is_active: bool = Field(default=True)
    roles: List[str] = Field(default=[], sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_column_kwargs={"onupdate": lambda: datetime.now(timezone.utc)})

    # OIDC fields
    oidc_sub: Optional[str] = Field(default=None, index=True)  # Subject identifier from OIDC
    oidc_issuer: Optional[str] = Field(default=None)  # Issuer URL
    oidc_email_verified: bool = Field(default=False)  # Email verified by IdP
    tenant_id: Optional[str] = Field(default=None, index=True)  # Tenant ID from OIDC claims

    # WebAuthn/Passkey credentials - JSON array of registered credentials
    passkey_credentials: List[Dict] = Field(default=[], sa_column=Column(JSON))

    apps: List["App"] = Relationship(back_populates="owner", sa_relationship_kwargs={"cascade": "all, delete-orphan"})
