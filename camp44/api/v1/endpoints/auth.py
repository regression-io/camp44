import hashlib
import html
import logging
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import httpx
import stripe
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from camp44 import crud
from camp44.api import deps
from camp44.core.auth_tokens import create_token_pair
from camp44.core.config import settings
from camp44.core.security import get_password_hash
from camp44.crud import refresh_token as rt_crud
from camp44.models.token import Token
from camp44.models.user import User, UserCreate, UserRead

# In-memory auth code store: code → {token_pair, created_at}
# Single-use, 60-second TTL. Fine for single-instance deployments.
_auth_codes: dict[str, dict] = {}
_auth_codes_lock = threading.Lock()


def _cleanup_expired_codes():
    """Remove codes older than 60s."""
    now = time.monotonic()
    expired = [k for k, v in _auth_codes.items() if now - v["created_at"] > 60]
    for k in expired:
        del _auth_codes[k]


def _create_auth_code(token_pair) -> str:
    """Generate a short-lived, single-use authorization code."""
    code = secrets.token_urlsafe(32)
    with _auth_codes_lock:
        _cleanup_expired_codes()
        _auth_codes[code] = {
            "access_token": token_pair.access_token,
            "refresh_token": token_pair.refresh_token,
            "created_at": time.monotonic(),
        }
    return code


_ALLOWED_REDIRECT_HOSTS = {
    "app.scalemate.regression.io",
    "gtm.scalemate.regression.io",
    "scalemate.regression.io",
    "app.scalemate.me",
    "gtm.scalemate.me",
    "scalemate.me",
    "localhost",
}


def _sanitize_redirect_url(url: str | None) -> str | None:
    """Validate redirect URL to prevent open redirect / XSS."""
    if not url:
        return None
    try:
        parsed = urlparse(url)
        if parsed.hostname and parsed.hostname not in _ALLOWED_REDIRECT_HOSTS:
            return None
        if parsed.scheme and parsed.scheme not in ("http", "https"):
            return None
        return url
    except Exception:
        return None


router = APIRouter()
logger = logging.getLogger(__name__)


class CodeExchangeRequest(BaseModel):
    """Request body for exchanging an auth code for tokens."""

    code: str


@router.post("/exchange-code", response_model=Token)
def exchange_code(body: CodeExchangeRequest):
    """
    Exchange a short-lived authorization code for access + refresh tokens.

    Codes are single-use and expire after 60 seconds.
    """
    with _auth_codes_lock:
        _cleanup_expired_codes()
        entry = _auth_codes.pop(body.code, None)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired authorization code",
        )

    return Token(
        access_token=entry["access_token"], refresh_token=entry["refresh_token"]
    )


async def send_welcome_email(email: str, name: str, setup_url: str) -> bool:
    """Send welcome email with password setup link via Base44."""
    if not settings.BASE44_API_KEY or not settings.BASE44_APP_ID:
        logger.warning("BASE44_API_KEY or BASE44_APP_ID not configured, skipping email")
        return False

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{settings.BASE44_API_URL}/apps/{settings.BASE44_APP_ID}/integration-endpoints/Core/SendEmail",
                headers={
                    "Content-Type": "application/json",
                    "api_key": settings.BASE44_API_KEY,
                },
                json={
                    "to": email,
                    "subject": "Welcome to ScaleMate - Set Up Your Account",
                    "body": f"""
Hi {name},

Welcome to ScaleMate! Your account has been created and your 7-day free trial has started.

To complete your account setup and log in, please set your password by clicking the link below:

{setup_url}

This link will expire in 7 days.

What's next:
- Set your password using the link above
- Log in to your dashboard at https://app.scalemate.regression.io
- Start exploring ScaleMate's features

If you have any questions, reply to this email or visit https://scalemate.regression.io/contact

Best,
The ScaleMate Team
""",
                    "from_name": "ScaleMate",
                },
            )

            if response.status_code == 200:
                logger.info(f"Welcome email sent to {email}")
                return True
            else:
                logger.error(
                    f"Failed to send welcome email to {email}: {response.text}"
                )
                return False

    except Exception as e:
        logger.error(f"Exception sending welcome email to {email}: {e}")
        return False


# Initialize Stripe
if settings.STRIPE_SECRET_KEY:
    stripe.api_key = settings.STRIPE_SECRET_KEY


class CheckoutRequest(BaseModel):
    """Request body for creating a Stripe checkout session."""

    email: EmailStr
    name: str
    plan: str  # "growth" or "scale"
    company: Optional[str] = None
    success_url: str
    cancel_url: str


class CheckoutResponse(BaseModel):
    """Response with Stripe checkout URL."""

    checkout_url: str
    session_id: str


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    from_url: str | None = None,
    app_id: str | None = None,
):
    """
    Serves a simple HTML login form.
    This is necessary because the Base44 SDK expects to GET the login endpoint,
    but our authentication flow expects a POST with form data.
    """
    logger.info(f"GET /login request with from_url={from_url}, app_id={app_id}")

    # Use provided parameters or get them from query string
    from_url = from_url or request.query_params.get(
        "from_url", "http://localhost:5173/"
    )
    app_id = app_id or request.query_params.get("app_id", "")

    # Escape user-controlled values before interpolating into HTML
    from_url = html.escape(from_url or "", quote=True)
    app_id = html.escape(app_id or "", quote=True)

    # Create a simple login form HTML that posts directly to /auth/login
    login_form = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login to ScaleMate</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
            .form-container {{ max-width: 400px; margin: 0 auto; padding: 30px; border: 1px solid #ddd; border-radius: 8px; background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            .form-group {{ margin-bottom: 20px; }}
            label {{ display: block; margin-bottom: 5px; font-weight: 500; }}
            input {{ width: 100%; padding: 12px; box-sizing: border-box; border: 1px solid #ddd; border-radius: 4px; }}
            button {{ width: 100%; padding: 12px; background: linear-gradient(to right, #059669, #2563eb); color: white; border: none; cursor: pointer; border-radius: 4px; font-size: 16px; }}
            button:hover {{ opacity: 0.9; }}
            .signup-link {{ margin-top: 20px; text-align: center; color: #666; }}
            .signup-link a {{ color: #059669; }}
        </style>
    </head>
    <body>
        <div class="form-container">
            <h2 style="text-align: center; margin-bottom: 30px;">Login to ScaleMate</h2>
            <form id="loginForm" action="/login" method="post">
                <input type="hidden" name="from_url" value="{from_url}">
                <input type="hidden" name="app_id" value="{app_id}">
                <div class="form-group">
                    <label for="username">Email</label>
                    <input type="email" id="username" name="username" placeholder="you@company.com" required>
                </div>
                <div class="form-group">
                    <label for="password">Password</label>
                    <input type="password" id="password" name="password" placeholder="Enter your password" required>
                </div>
                <button type="submit">Sign In</button>
            </form>
            <p class="signup-link">Don't have an account? <a href="https://scalemate.regression.io/signup">Start your free trial</a></p>
        </div>
    </body>
    </html>
    '''
    return HTMLResponse(content=login_form)


@router.post("/login", response_model=Token)
def login(
    db: Session = Depends(deps.get_db),
    form_data: OAuth2PasswordRequestForm = Depends(),
    from_url: str = Form(None),
    app_id: str = Form(None),
    request: Request = None,
) -> Token:
    """Logs a user in."""
    logger.info(f"POST /login request for username={form_data.username}")

    # Check if user exists but has no password (migrated account)
    existing_user = crud.user.get_user_by_email(session=db, email=form_data.username)
    if existing_user and not existing_user.hashed_password:
        logger.info(f"Login attempt for passwordless account {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="password_not_set",
        )

    user = crud.user.authenticate(
        session=db, email=form_data.username, password=form_data.password
    )
    if not user:
        logger.error(f"Authentication failed for {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    elif not user.is_active:
        logger.error(f"User {form_data.username} is inactive")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )

    logger.info(f"Authentication successful for {form_data.username}")
    token_pair = create_token_pair(db, user)

    # Sanitize from_url to prevent open redirect / XSS
    from_url = _sanitize_redirect_url(from_url)
    if from_url:
        logger.info(f"Creating code-based redirect to {from_url}")
        code = _create_auth_code(token_pair)
        separator = "&" if "?" in from_url else "?"
        redirect_url = f"{from_url}{separator}code={code}"

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <meta http-equiv="refresh" content="0;url={redirect_url}">
        </head>
        <body>
            <h2>Authentication Successful</h2>
            <p>Redirecting to application...</p>
        </body>
        </html>
        """

        response = HTMLResponse(content=html_content)
        logger.info(
            f"Login successful for {form_data.username}, redirecting with auth code"
        )
        return response

    logger.info(f"Returning token for {form_data.username} without redirect")
    return token_pair


@router.post("/register", response_model=UserRead)
def register(*, db: Session = Depends(deps.get_db), user_in: UserCreate) -> User:
    """Registers a new user."""
    user = crud.user.get_user_by_email(session=db, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The user with this email already exists in the system.",
        )
    user = crud.user.create_user(session=db, user_in=user_in)
    return user


# Stripe price IDs for ScaleMate plans (from environment config)
def get_plan_prices():
    """Get plan prices from settings."""
    return {
        "growth": {
            "price_id": settings.STRIPE_GROWTH_PRICE_ID,
            "name": "Growth",
        },
        "scale": {
            "price_id": settings.STRIPE_SCALE_PRICE_ID,
            "name": "Scale",
        },
    }


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout_session(
    *,
    db: Session = Depends(deps.get_db),
    checkout_request: CheckoutRequest,
) -> CheckoutResponse:
    """
    Create a Stripe checkout session for subscription signup.

    This endpoint:
    1. Creates or retrieves the user
    2. Creates a Stripe customer
    3. Creates a checkout session with 7-day trial
    4. Returns the checkout URL
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    plan_info = get_plan_prices().get(checkout_request.plan.lower())
    if not plan_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {checkout_request.plan}. Must be 'growth' or 'scale'.",
        )

    # Check if user exists
    user = crud.user.get_user_by_email(session=db, email=checkout_request.email)

    if user:
        # User exists - use their Stripe customer ID or create one
        if not user.stripe_customer_id:
            customer = stripe.Customer.create(
                email=checkout_request.email,
                name=checkout_request.name,
                metadata={
                    "user_id": str(user.id),
                    "company": checkout_request.company or "",
                },
            )
            user.stripe_customer_id = customer.id
            db.add(user)
            db.commit()
        stripe_customer_id = user.stripe_customer_id
    else:
        # Create Stripe customer first (user will be created on webhook)
        customer = stripe.Customer.create(
            email=checkout_request.email,
            name=checkout_request.name,
            metadata={
                "company": checkout_request.company or "",
                "pending_signup": "true",
            },
        )
        stripe_customer_id = customer.id

    # Create Stripe checkout session
    try:
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            line_items=[
                {
                    "price": plan_info["price_id"],
                    "quantity": 1,
                },
            ],
            mode="subscription",
            subscription_data={
                # trial_period_days removed — F31 manages trial at app level
                "metadata": {
                    "plan": checkout_request.plan,
                    "customer_name": checkout_request.name,
                    "company": checkout_request.company or "",
                },
            },
            success_url=checkout_request.success_url
            + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=checkout_request.cancel_url,
            allow_promotion_codes=True,
        )

        logger.info(
            f"Created checkout session {session.id} for {checkout_request.email}"
        )

        if not session.url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Stripe session URL not available",
            )

        return CheckoutResponse(
            checkout_url=session.url,
            session_id=session.id,
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe error for {checkout_request.email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Payment service temporarily unavailable. Please try again.",
        )


@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(deps.get_db)):
    """
    Handle Stripe webhook events.

    Processes:
    - checkout.session.completed: Creates user account after successful payment
    - customer.subscription.deleted: Handles subscription cancellation
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    if not sig_header:
        logger.warning("Stripe webhook missing signature header")
        raise HTTPException(status_code=400, detail="Missing signature header")

    # Always require webhook secret - no bypass
    if not settings.STRIPE_WEBHOOK_SECRET:
        logger.error("STRIPE_WEBHOOK_SECRET not configured - rejecting webhook")
        raise HTTPException(status_code=500, detail="Webhook not configured")

    # Verify webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.type
    event_id = event.id
    logger.info(f"Processing Stripe webhook: {event_type} (event_id={event_id})")

    # Handle checkout.session.completed - create user account
    if event_type == "checkout.session.completed":
        session_obj = event.data.object
        customer_id = session_obj.get("customer")
        subscription_id = session_obj.get("subscription")

        if not customer_id:
            logger.error("Webhook checkout.session.completed missing customer_id")
            raise HTTPException(status_code=400, detail="Missing customer_id")

        # Check idempotency - if user already has this customer_id, skip
        existing_by_stripe = crud.user.get_by_stripe_customer_id(
            session=db, customer_id=customer_id
        )
        if existing_by_stripe:
            logger.info(f"Webhook already processed for customer {customer_id}")
            return {"status": "success", "message": "Already processed"}

        # Get customer details from Stripe
        try:
            customer = stripe.Customer.retrieve(customer_id)
        except stripe.StripeError as e:
            logger.error(f"Failed to retrieve Stripe customer {customer_id}: {e}")
            # Return 500 so Stripe retries
            raise HTTPException(status_code=500, detail="Failed to retrieve customer")

        email = customer.email
        if not email:
            logger.error(f"Stripe customer {customer_id} has no email")
            # Permanent failure - don't retry
            raise HTTPException(status_code=400, detail="Customer has no email")

        name = customer.name or email.split("@")[0]

        # Check if user already exists by email
        existing_user = crud.user.get_user_by_email(session=db, email=email)
        if existing_user:
            # Update existing user with subscription info
            existing_user.stripe_customer_id = customer_id
            existing_user.stripe_subscription_id = subscription_id
            db.add(existing_user)
            db.commit()
            logger.info(
                f"Updated existing user {email} with subscription {subscription_id}"
            )
            return {"status": "success", "message": "User updated"}

        # Generate a password reset token (user will set their own password)
        reset_token = secrets.token_urlsafe(32)
        reset_expires = datetime.now(timezone.utc) + timedelta(
            days=7
        )  # Token valid for 7 days

        # Generate a random password (user won't use this directly)
        temp_password = secrets.token_urlsafe(32)

        # Create the user
        user_in = UserCreate(
            email=email,
            password=temp_password,
            display_name=name,
        )

        try:
            new_user = crud.user.create_user(session=db, user_in=user_in)
            new_user.stripe_customer_id = customer_id
            new_user.stripe_subscription_id = subscription_id
            new_user.password_reset_token = hashlib.sha256(
                reset_token.encode()
            ).hexdigest()
            new_user.password_reset_expires = reset_expires
            db.add(new_user)
            db.commit()
            logger.info(
                f"Created new user {email} from Stripe checkout with reset token"
            )

            # Send welcome email with password setup link
            frontend_url = (
                getattr(settings, "FRONTEND_URL", None)
                or "https://app.scalemate.regression.io"
            )
            setup_url = f"{frontend_url}/set-password?token={reset_token}"
            await send_welcome_email(email, name, setup_url)

            return {
                "status": "success",
                "message": "User created",
                "user_id": str(new_user.id),
            }
        except Exception as e:
            logger.error(f"Failed to create user {email}: {e}")
            db.rollback()
            # Return 500 so Stripe retries
            raise HTTPException(status_code=500, detail="Failed to create user")

    # Handle subscription deleted - deactivate user
    elif event_type == "customer.subscription.deleted":
        subscription_obj = event.data.object
        customer_id = subscription_obj.get("customer")

        if not customer_id:
            logger.warning("Subscription deleted event missing customer_id")
            return {"status": "success", "message": "No customer_id"}

        # Find user by stripe_customer_id and deactivate
        user = crud.user.get_by_stripe_customer_id(session=db, customer_id=customer_id)
        if user:
            user.is_active = False
            user.stripe_subscription_id = None
            db.add(user)
            db.commit()
            logger.info(
                f"Deactivated user {user.email} due to subscription cancellation"
            )
            return {"status": "success", "message": "User deactivated"}
        else:
            logger.warning(
                f"No user found for cancelled subscription customer {customer_id}"
            )
            return {"status": "success", "message": "User not found"}

    # Return success for unhandled events
    return {"status": "success", "message": f"Unhandled event type: {event_type}"}


class SetPasswordRequest(BaseModel):
    """Request body for setting password with reset token."""

    token: str
    password: str = Field(min_length=8)


class SetPasswordResponse(BaseModel):
    """Response after setting password."""

    success: bool
    message: str


class SetupLinkRequest(BaseModel):
    """Request body for getting password setup link from checkout session."""

    session_id: str


class SetupLinkResponse(BaseModel):
    """Response with password setup information."""

    success: bool
    setup_url: Optional[str] = None
    email: Optional[str] = None
    message: str


@router.post("/get-setup-link", response_model=SetupLinkResponse)
def get_setup_link(
    *,
    db: Session = Depends(deps.get_db),
    request: SetupLinkRequest,
) -> SetupLinkResponse:
    """
    Get the password setup link for a user created from a Stripe checkout session.

    This is called from the Success page after checkout completes.
    The session_id provides proof of payment, so we can safely return the setup link.
    """
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe is not configured",
        )

    try:
        # Retrieve the checkout session from Stripe
        session_obj = stripe.checkout.Session.retrieve(request.session_id)
    except stripe.InvalidRequestError:
        return SetupLinkResponse(
            success=False,
            message="Invalid session ID",
        )
    except stripe.StripeError as e:
        logger.error(f"Stripe error retrieving session: {e}")
        return SetupLinkResponse(
            success=False,
            message="Unable to verify session",
        )

    customer_id = session_obj.get("customer")
    if not customer_id:
        return SetupLinkResponse(
            success=False,
            message="Session has no customer",
        )

    # Find user by stripe_customer_id
    user = crud.user.get_by_stripe_customer_id(session=db, customer_id=customer_id)
    if not user:
        # User might not be created yet if webhook hasn't fired
        return SetupLinkResponse(
            success=False,
            message="Account is being set up. Please wait a moment and try again.",
        )

    # Check if user already has a password set (no reset token)
    if not user.password_reset_token:
        return SetupLinkResponse(
            success=True,
            email=user.email,
            message="Password already set. Please log in.",
        )

    # Token is stored hashed — we can't reconstruct the URL. Direct user to email.
    return SetupLinkResponse(
        success=True,
        email=user.email,
        message="A password setup link was sent to your email. Please check your inbox.",
    )


@router.post("/set-password", response_model=SetPasswordResponse)
def set_password(
    *,
    db: Session = Depends(deps.get_db),
    request: SetPasswordRequest,
) -> SetPasswordResponse:
    """
    Set password using a reset token.

    This is used after Stripe checkout to allow users to set their password.
    """
    # Find user by reset token
    user = crud.user.get_by_password_reset_token(session=db, token=request.token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    # Check if token is expired
    # Handle both naive (TIMESTAMP) and aware (TIMESTAMPTZ) datetimes from DB
    expires = user.password_reset_expires
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired",
        )

    # Update password, clear reset token, and activate user
    user.hashed_password = get_password_hash(request.password)
    user.password_reset_token = None
    user.password_reset_expires = None
    user.is_active = True
    db.add(user)
    db.commit()

    logger.info(f"Password set for user {user.email}")
    return SetPasswordResponse(success=True, message="Password set successfully")


class ForgotPasswordRequest(BaseModel):
    """Request body for forgot password."""

    email: EmailStr


@router.post("/forgot-password")
def forgot_password(
    *,
    db: Session = Depends(deps.get_db),
    request: ForgotPasswordRequest,
):
    """
    Request a password reset email.

    Always returns 200 regardless of whether the email exists (prevents enumeration).
    """
    user = crud.user.get_user_by_email(session=db, email=request.email)
    if user and user.is_active:
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token = hashlib.sha256(reset_token.encode()).hexdigest()
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=24)
        db.add(user)
        db.commit()

        frontend_url = (
            getattr(settings, "FRONTEND_URL", None)
            or "https://app.scalemate.regression.io"
        )
        reset_url = f"{frontend_url}/set-password?token={reset_token}"

        if settings.BASE44_API_KEY and settings.BASE44_APP_ID:
            try:
                with httpx.Client(timeout=30.0) as client:
                    client.post(
                        f"{settings.BASE44_API_URL}/apps/{settings.BASE44_APP_ID}/integration-endpoints/Core/SendEmail",
                        headers={
                            "Content-Type": "application/json",
                            "api_key": settings.BASE44_API_KEY,
                        },
                        json={
                            "to": user.email,
                            "subject": "ScaleMate - Reset Your Password",
                            "body": (
                                f"<h2>Password Reset</h2>"
                                f"<p>Hi {user.display_name or 'there'},</p>"
                                f"<p>We received a request to reset your password. "
                                f"Click the link below to set a new password:</p>"
                                f'<p><a href="{reset_url}" style="color: #059669; font-weight: bold;">'
                                f"Reset Password</a></p>"
                                f"<p>This link expires in 24 hours.</p>"
                                f"<p>If you didn't request this, you can safely ignore this email.</p>"
                                f"<p>— The ScaleMate Team</p>"
                            ),
                            "from_name": "ScaleMate",
                        },
                    )
                logger.info(f"Password reset email sent to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send reset email to {user.email}: {e}")
        else:
            logger.warning(
                "BASE44_API_KEY or BASE44_APP_ID not configured, skipping reset email"
            )

    return {
        "message": "If an account with that email exists, a password reset link has been sent."
    }


class RefreshRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str


@router.post("/refresh", response_model=Token)
def refresh(
    *,
    db: Session = Depends(deps.get_db),
    body: RefreshRequest,
) -> Token:
    """
    Exchange a valid refresh token for a new token pair.

    Implements rotation: the old refresh token is consumed and replaced.
    If a consumed (already-used) token is presented, the entire family is
    revoked to protect against token replay.
    """
    _INVALID = "Invalid or expired refresh token"

    stored = rt_crud.get_by_token(db, raw_token=body.refresh_token)
    if not stored:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    # Reuse detection: token already consumed → revoke the whole family
    if stored.is_revoked:
        rt_crud.revoke_family(db, family_id=stored.family_id)
        db.commit()
        logger.warning(
            "Refresh token reuse detected for user %s, family %s",
            stored.user_id,
            stored.family_id,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    expires = (
        stored.expires_at.replace(tzinfo=timezone.utc)
        if stored.expires_at.tzinfo is None
        else stored.expires_at
    )
    if expires < datetime.now(timezone.utc):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    user = crud.user.get(db, id=stored.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    # Version mismatch → user's tokens were revoked globally
    if stored.token_version != user.token_version:
        rt_crud.revoke_family(db, family_id=stored.family_id)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=_INVALID)

    # Atomically: consume old token + create new pair in one commit
    stored.is_revoked = True
    db.add(stored)
    # create_token_pair flushes the new token then commits both ops together
    token_pair = create_token_pair(db, user, family_id=stored.family_id)
    return token_pair


class LogoutRequest(BaseModel):
    """Request body for logout."""

    refresh_token: str


@router.post("/logout")
def logout(
    *,
    db: Session = Depends(deps.get_db),
    body: LogoutRequest,
):
    """Revoke the refresh token (server-side logout)."""
    stored = rt_crud.get_by_token(db, raw_token=body.refresh_token)
    if stored and not stored.is_revoked:
        stored.is_revoked = True
        db.add(stored)
        db.commit()
    return {"detail": "Logged out"}
