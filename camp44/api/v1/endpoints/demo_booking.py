"""Demo booking endpoints.

Allows users to book demo calls and admins to manage availability.
"""
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import logging
import httpx

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from camp44.api import deps
from camp44.core.config import settings
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
    "buffer_minutes": 15,  # Buffer between slots
    "advance_days": 14,  # How far ahead users can book
    "blocked_dates": [],  # Dates to block (ISO format)
}

# In-memory storage for availability config (in production, use database)
# This could be moved to an Entity or dedicated table
_availability_config = DEFAULT_AVAILABILITY.copy()
_booked_slots: List[str] = []  # List of booked datetime ISO strings


class AvailabilityConfig(BaseModel):
    """Configuration for demo availability."""
    timezone: str = "America/New_York"
    weekly_schedule: dict = Field(default_factory=dict)
    slot_duration_minutes: int = 30
    buffer_minutes: int = 15
    advance_days: int = 14
    blocked_dates: List[str] = Field(default_factory=list)


class TimeSlot(BaseModel):
    """A single available time slot."""
    datetime_utc: str  # ISO format
    datetime_local: str  # Display format
    date: str  # YYYY-MM-DD
    time: str  # HH:MM
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
    slot_datetime: str  # ISO format datetime
    message: Optional[str] = None


class BookDemoResponse(BaseModel):
    """Response after booking a demo."""
    success: bool
    message: str
    booking_datetime: Optional[str] = None


def generate_time_slots(config: dict, start_date: datetime, days: int) -> List[TimeSlot]:
    """Generate available time slots based on configuration."""
    slots = []
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]

    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = current + timedelta(days=days)

    while current < end_date:
        day_name = day_names[current.weekday()]
        day_schedule = config.get("weekly_schedule", {}).get(day_name)

        if day_schedule:
            # Check if date is blocked
            date_str = current.strftime("%Y-%m-%d")
            if date_str in config.get("blocked_dates", []):
                current += timedelta(days=1)
                continue

            # Parse start and end times
            start_hour, start_min = map(int, day_schedule["start"].split(":"))
            end_hour, end_min = map(int, day_schedule["end"].split(":"))

            slot_time = current.replace(hour=start_hour, minute=start_min)
            end_time = current.replace(hour=end_hour, minute=end_min)

            slot_duration = config.get("slot_duration_minutes", 30)
            buffer = config.get("buffer_minutes", 15)

            while slot_time < end_time:
                # Check if slot is in the past
                if slot_time > datetime.now(timezone.utc).replace(tzinfo=None):
                    slot_iso = slot_time.isoformat() + "Z"
                    is_available = slot_iso not in _booked_slots

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
def get_available_slots() -> AvailableSlotsResponse:
    """
    Get available demo time slots for the next N days.

    Returns slots based on the configured weekly schedule,
    excluding blocked dates and already booked slots.
    """
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    # Start from tomorrow
    start_date = now + timedelta(days=1)

    slots = generate_time_slots(
        _availability_config,
        start_date,
        _availability_config.get("advance_days", 14)
    )

    return AvailableSlotsResponse(
        slots=slots,
        timezone=_availability_config.get("timezone", "America/New_York"),
        slot_duration_minutes=_availability_config.get("slot_duration_minutes", 30),
    )


@router.post("/book", response_model=BookDemoResponse)
async def book_demo(request: BookDemoRequest) -> BookDemoResponse:
    """
    Book a demo slot and send confirmation emails.

    Sends email to sales@regression.io with booking details.
    """
    # Validate slot is available
    if request.slot_datetime in _booked_slots:
        raise HTTPException(
            status_code=400,
            detail="This time slot is no longer available. Please choose another."
        )

    # Parse the datetime for display
    try:
        slot_dt = datetime.fromisoformat(request.slot_datetime.replace("Z", "+00:00"))
        display_time = slot_dt.strftime("%B %d, %Y at %I:%M %p UTC")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")

    # Mark slot as booked
    _booked_slots.append(request.slot_datetime)

    # Send email notification to sales via Base44
    email_sent = await send_demo_booking_email(
        name=request.name,
        email=request.email,
        company=request.company,
        phone=request.phone,
        slot_datetime=display_time,
        message=request.message,
    )

    if not email_sent:
        logger.warning(f"Failed to send demo booking email for {request.email}")
        # Still return success - booking is recorded

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

    # Build email body
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
                    "reply_to": email,  # So replies go to the customer
                },
            )

            if response.status_code == 200:
                logger.info(f"Demo booking email sent for {email}")
                return True
            else:
                logger.error(f"Failed to send demo booking email: {response.text}")
                return False

    except Exception as e:
        logger.error(f"Exception sending demo booking email: {e}")
        return False


# Admin endpoints for managing availability
@router.get("/admin/config", response_model=AvailabilityConfig)
def get_availability_config(
    current_user: User = Depends(deps.get_current_active_user),
) -> AvailabilityConfig:
    """Get current availability configuration (admin only)."""
    # Check if user is admin (has admin role)
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")

    return AvailabilityConfig(**_availability_config)


@router.put("/admin/config", response_model=AvailabilityConfig)
def update_availability_config(
    config: AvailabilityConfig,
    current_user: User = Depends(deps.get_current_active_user),
) -> AvailabilityConfig:
    """Update availability configuration (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")

    global _availability_config
    _availability_config = config.model_dump()
    logger.info(f"Availability config updated by {current_user.email}")

    return config


@router.post("/admin/block-date")
def block_date(
    date: str,  # YYYY-MM-DD format
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Block a specific date from booking (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")

    # Validate date format
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    if date not in _availability_config["blocked_dates"]:
        _availability_config["blocked_dates"].append(date)
        logger.info(f"Date {date} blocked by {current_user.email}")

    return {"success": True, "blocked_dates": _availability_config["blocked_dates"]}


@router.delete("/admin/block-date")
def unblock_date(
    date: str,
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Unblock a specific date (admin only)."""
    if "admin" not in (current_user.roles or []):
        raise HTTPException(status_code=403, detail="Admin access required")

    if date in _availability_config["blocked_dates"]:
        _availability_config["blocked_dates"].remove(date)
        logger.info(f"Date {date} unblocked by {current_user.email}")

    return {"success": True, "blocked_dates": _availability_config["blocked_dates"]}
