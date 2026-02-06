"""Demo booking endpoints.

Allows users to book demo calls and admins to manage availability.
All state is persisted in the database (DemoBooking + DemoAvailabilityConfig tables).
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging
import httpx

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlmodel import Session, select

from camp44.api import deps
from camp44.core.config import settings
from camp44.models.demo_booking import DemoAvailabilityConfig, DemoBooking
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


def _get_booked_slots(db: Session) -> set[str]:
    """Return set of booked slot_datetime strings."""
    results = db.exec(select(DemoBooking.slot_datetime)).all()
    return set(results)


class AvailabilityConfigSchema(BaseModel):
    """Configuration for demo availability."""
    timezone: str = "America/New_York"
    weekly_schedule: dict = Field(default_factory=dict)
    slot_duration_minutes: int = 30
    buffer_minutes: int = 15
    advance_days: int = 14
    blocked_dates: List[str] = Field(default_factory=list)


class TimeSlot(BaseModel):
    """A single available time slot."""
    datetime_utc: str
    datetime_local: str
    date: str
    time: str
    available: bool = True


class AvailableSlotsResponse(BaseModel):
    """Response with available time slots."""
    slots: List[TimeSlot]
    timezone: str
    slot_duration_minutes: int


class BookDemoRequest(BaseModel):
    """Request to book a demo."""
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    company: Optional[str] = None
    phone: Optional[str] = None
    slot_datetime: str
    message: Optional[str] = None


class BookDemoResponse(BaseModel):
    """Response after booking a demo."""
    success: bool
    message: str
    booking_datetime: Optional[str] = None


def generate_time_slots(
    config: dict, start_date: datetime, days: int, booked_slots: set[str]
) -> List[TimeSlot]:
    """Generate available time slots based on configuration."""
    slots = []
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = current + timedelta(days=days)

    while current < end_date:
        day_name = day_names[current.weekday()]
        day_schedule = config.get("weekly_schedule", {}).get(day_name)

        if day_schedule:
            date_str = current.strftime("%Y-%m-%d")
            if date_str in config.get("blocked_dates", []):
                current += timedelta(days=1)
                continue

            start_hour, start_min = map(int, day_schedule["start"].split(":"))
            end_hour, end_min = map(int, day_schedule["end"].split(":"))

            slot_time = current.replace(hour=start_hour, minute=start_min)
            end_time = current.replace(hour=end_hour, minute=end_min)

            slot_duration = config.get("slot_duration_minutes", 30)
            buffer = config.get("buffer_minutes", 15)

            while slot_time < end_time:
                if slot_time > datetime.now(timezone.utc).replace(tzinfo=None):
                    slot_iso = slot_time.isoformat() + "Z"
                    is_available = slot_iso not in booked_slots

                    slots.append(TimeSlot(
                        datetime_utc=slot_iso,
                        datetime_local=slot_time.strftime("%B %d, %Y at %I:%M %p"),
                        date=date_str,
                        time=slot_time.strftime("%H:%M"),
                        available=is_available,
                    ))

                slot_time += timedelta(minutes=slot_duration + buffer)

        current += timedelta(days=1)

    return slots


@router.get("/slots", response_model=AvailableSlotsResponse)
def get_available_slots(
    db: Session = Depends(deps.get_db),
) -> AvailableSlotsResponse:
    """Get available demo time slots for the next N days."""
    config = _get_availability_config(db)
    booked = _get_booked_slots(db)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    start_date = now + timedelta(days=1)

    slots = generate_time_slots(
        config, start_date, config.get("advance_days", 14), booked
    )

    return AvailableSlotsResponse(
        slots=slots,
        timezone=config.get("timezone", "America/New_York"),
        slot_duration_minutes=config.get("slot_duration_minutes", 30),
    )


@router.post("/book", response_model=BookDemoResponse)
async def book_demo(
    request: BookDemoRequest,
    db: Session = Depends(deps.get_db),
) -> BookDemoResponse:
    """Book a demo slot and send confirmation email."""
    # Check if slot is already booked
    existing = db.exec(
        select(DemoBooking).where(DemoBooking.slot_datetime == request.slot_datetime)
    ).first()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="This time slot is no longer available. Please choose another."
        )

    try:
        slot_dt = datetime.fromisoformat(request.slot_datetime.replace("Z", "+00:00"))
        display_time = slot_dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    # Persist booking
    booking = DemoBooking(
        name=request.name,
        email=request.email,
        company=request.company,
        phone=request.phone,
        slot_datetime=request.slot_datetime,
        message=request.message,
    )
    db.add(booking)
    db.commit()

    # Send email notification (best-effort)
    email_sent = await send_demo_booking_email(
        name=request.name,
        email=request.email,
        company=request.company,
        phone=request.phone,
        slot_datetime=display_time,
        message=request.message,
    )
    if not email_sent:
        logger.warning("Failed to send demo booking email for %s", request.email)

    return BookDemoResponse(
        success=True,
        message=f"Demo booked successfully for {display_time}. You'll receive a confirmation email shortly.",
        booking_datetime=request.slot_datetime,
    )


async def send_demo_booking_email(
    name: str,
    email: str,
    company: Optional[str],
    phone: Optional[str],
    slot_datetime: str,
    message: Optional[str],
) -> bool:
    """Send demo booking notification to sales@regression.io via Base44."""
    if not settings.BASE44_API_KEY or not settings.BASE44_APP_ID:
        logger.warning("BASE44 credentials not configured, skipping email")
        return False

    body = f"""New Demo Booking Request

Name: {name}
Email: {email}
Company: {company or 'Not provided'}
Phone: {phone or 'Not provided'}
Requested Time: {slot_datetime}

Message:
{message or 'No message provided'}

---
Please follow up to confirm the demo appointment.
Add a calendar invite and send confirmation to the customer.
"""

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.BASE44_API_URL}/apps/{settings.BASE44_APP_ID}/integration-endpoints/Core/SendEmail",
                headers={
                    "Content-Type": "application/json",
                    "api_key": settings.BASE44_API_KEY,
                },
                json={
                    "to": "sales@regression.io",
                    "subject": f"Demo Request: {name} from {company or 'Unknown Company'} - {slot_datetime}",
                    "body": body,
                    "from_name": "ScaleMate Demo Booking",
                    "reply_to": email,
                },
            )

            if response.status_code == 200:
                logger.info("Demo booking email sent for %s", email)
                return True
            else:
                logger.error("Failed to send demo booking email: %s", response.text)
                return False

    except Exception as e:
        logger.error("Exception sending demo booking email: %s", e)
        return False


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
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

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
