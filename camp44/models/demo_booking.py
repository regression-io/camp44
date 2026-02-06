"""Demo booking models - persistent storage for demo bookings and availability config."""
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from sqlalchemy import Column
from sqlalchemy import JSON
from sqlmodel import Field, SQLModel


class DemoBooking(SQLModel, table=True):
    """A booked demo slot."""
    __tablename__ = "demo_bookings"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str
    email: str = Field(index=True)
    company: str | None = None
    phone: str | None = None
    slot_datetime: str = Field(unique=True, index=True)  # ISO format
    message: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DemoAvailabilityConfig(SQLModel, table=True):
    """Single-row table storing demo availability configuration."""
    __tablename__ = "demo_availability_config"

    id: int = Field(default=1, primary_key=True)
    config: Dict[str, Any] = Field(default={}, sa_column=Column(JSON))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
