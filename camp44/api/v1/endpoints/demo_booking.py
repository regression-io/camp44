"""
Demo availability admin endpoints.

Manages demo availability config (timezone, weekly schedule, blocked dates).
Public booking endpoints (/slots, /book) and their email-out helper were
removed 2026-05-24 — the AI frontend's AdminDemoAvailability.jsx is the
only remaining consumer, and it uses only the /admin/* sub-routes here.
See archive/unused-public-routes-2026-05-24 branch for the deleted code
and scalemate-service/docs/security/2026-05-24-audit.md P2-13 (mooted).
"""

import logging
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session

from camp44.api import deps
from camp44.models.demo_booking import DemoAvailabilityConfig
from camp44.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


# Default availability: Mon-Fri, 9am-5pm EST
DEFAULT_AVAILABILITY = {
    "timezone": "America/New_York",
    "weekly_schedule": {
        "monday": {"start": "09:00", "end": "17:00"},
        "tuesday": {"start": "09:00", "end": "17:00"},
        "wednesday": {"start": "09:00", "end": "17:00"},
        "thursday": {"start": "09:00", "end": "17:00"},
        "friday": {"start": "09:00", "end": "17:00"},
    },
    "slot_duration_minutes": 30,
    "buffer_minutes": 15,
    "advance_days": 14,
    "blocked_dates": [],
}


def _get_availability_config(db: Session) -> dict:
    """Load availability config from DB, or return defaults if not yet stored."""
    row = db.get(DemoAvailabilityConfig, 1)
    if row and row.config:
        return row.config
    return DEFAULT_AVAILABILITY.copy()


def _save_availability_config(db: Session, config: dict) -> None:
    """Upsert the single-row availability config."""
    row = db.get(DemoAvailabilityConfig, 1)
    if row:
        row.config = config
        row.updated_at = datetime.now(timezone.utc)
    else:
        row = DemoAvailabilityConfig(id=1, config=config)
    db.add(row)
    db.commit()


class AvailabilityConfigSchema(BaseModel):
    """Configuration for demo availability."""

    timezone: str = "America/New_York"
    weekly_schedule: dict = Field(default_factory=dict)
    slot_duration_minutes: int = 30
    buffer_minutes: int = 15
    advance_days: int = 14
    blocked_dates: List[str] = Field(default_factory=list)


# Admin endpoints
@router.get("/admin/config", response_model=AvailabilityConfigSchema)
def get_admin_config(
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> AvailabilityConfigSchema:
    """Get current availability configuration (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")
    config = _get_availability_config(db)
    return AvailabilityConfigSchema(**config)


@router.put("/admin/config", response_model=AvailabilityConfigSchema)
def update_admin_config(
    config: AvailabilityConfigSchema,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> AvailabilityConfigSchema:
    """Update availability configuration (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")
    _save_availability_config(db, config.model_dump())
    logger.info("Availability config updated by %s", current_user.email)
    return config


@router.post("/admin/block-date")
def block_date(
    date: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Block a specific date from booking (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="Invalid date format. Use YYYY-MM-DD"
        )

    config = _get_availability_config(db)
    if date not in config.get("blocked_dates", []):
        config.setdefault("blocked_dates", []).append(date)
        _save_availability_config(db, config)
        logger.info("Date %s blocked by %s", date, current_user.email)

    return {"success": True, "blocked_dates": config.get("blocked_dates", [])}


@router.delete("/admin/block-date")
def unblock_date(
    date: str,
    db: Session = Depends(deps.get_db),
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Unblock a specific date (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")

    config = _get_availability_config(db)
    blocked = config.get("blocked_dates", [])
    if date in blocked:
        blocked.remove(date)
        config["blocked_dates"] = blocked
        _save_availability_config(db, config)
        logger.info("Date %s unblocked by %s", date, current_user.email)

    return {"success": True, "blocked_dates": config.get("blocked_dates", [])}
