import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String
from sqlmodel import Field, SQLModel


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_token"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    token_hash: str = Field(
        sa_column=Column(String, unique=True, index=True, nullable=False)
    )
    user_id: uuid.UUID = Field(foreign_key="user.id", index=True)
    family_id: uuid.UUID = Field(index=True)
    token_version: int = Field(default=0)
    is_revoked: bool = Field(default=False)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime
