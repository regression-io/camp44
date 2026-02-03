from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
import logging
import secrets
import stripe

from camp44 import crud
from camp44.api import deps
from camp44.core.security import create_access_token, get_password_hash
from camp44.core.config import settings
from camp44.models.token import Token
from camp44.models.user import User, UserCreate

router = APIRouter()
logger = logging.getLogger(__name__)

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
    from_url: str = None,
    app_id: str = None,
):
    """
    Serves a simple HTML login form.
    This is necessary because the Base44 SDK expects to GET the login endpoint,
    but our authentication flow expects a POST with form data.
    """
    logger.info(f"GET /login request with from_url={from_url}, app_id={app_id}")
    
    # Use provided parameters or get them from query string
    from_url = from_url or request.query_params.get("from_url", "http://localhost:5173/")
    app_id = app_id or request.query_params.get("app_id", "")
    
    # Create a simple login form HTML that posts directly to /auth/login
    login_form = f'''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Login to Cofounder Workshop</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            .form-container {{ max-width: 400px; margin: 0 auto; padding: 20px; border: 1px solid #ccc; border-radius: 5px; }}
            .form-group {{ margin-bottom: 15px; }}
            label {{ display: block; margin-bottom: 5px; }}
            input {{ width: 100%; padding: 8px; box-sizing: border-box; }}
            button {{ padding: 10px 15px; background-color: #4CAF50; color: white; border: none; cursor: pointer; }}
            .note {{ margin-top: 20px; font-size: 0.9em; color: #666; }}
        </style>
        <script>
            // Immediately store default credentials in the form when the page loads
            window.onload = function() {{
                document.getElementById('username').value = 'admin@example.com';
                document.getElementById('password').value = 'password';
            }}
        </script>
    </head>
    <body>
        <div class="form-container">
            <h2>Login to Cofounder Workshop</h2>
            <form id="loginForm" action="/login" method="post">
                <input type="hidden" name="from_url" value="{from_url}">
                <input type="hidden" name="app_id" value="{app_id}">
                <div class="form-group">
                    <label for="username">Email:</label>
                    <input type="email" id="username" name="username" value="admin@example.com" required>
                </div>
                <div class="form-group">
                    <label for="password">Password:</label>
                    <input type="password" id="password" name="password" value="password" required>
                </div>
                <button type="submit">Login</button>
            </form>
            <p class="note"><strong>Default login:</strong> admin@example.com / password</p>
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
    logger.info(f"POST /login request with username={form_data.username}, from_url={from_url}, app_id={app_id}")
    
    # Debug request headers and cookies if available
    if request:
        logger.info(f"Headers: {dict(request.headers)}")
    
    user = crud.user.authenticate(
        session=db, email=form_data.username, password=form_data.password
    )
    if not user:
        logger.error(f"Authentication failed for {form_data.username}")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    elif not user.is_active:
        logger.error(f"User {form_data.username} is inactive")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user"
        )
        
    logger.info(f"Authentication successful for {form_data.username}")
    access_token = create_access_token(data={"sub": str(user.id)})
    
    # Instead of simple redirect, create a special page that will:
    # 1. Set localStorage.token for JS libraries that expect it there
    # 2. Set cookies for API calls
    # 3. Redirect to the original URL
    if from_url:
        logger.info(f"Creating JS-enhanced redirect page to {from_url}")
        
        html_content = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Authentication Successful</title>
            <script>
                // Store token in localStorage for SDK access
                localStorage.setItem('token', '{access_token}');
                localStorage.setItem('access_token', '{access_token}');
                localStorage.setItem('auth_token', '{access_token}');
                
                // Also store in sessionStorage
                sessionStorage.setItem('token', '{access_token}');
                sessionStorage.setItem('access_token', '{access_token}');
                
                // Set a cookie via JavaScript (in addition to the HTTP-only cookies)
                document.cookie = "token=" + '{access_token}' + "; path=/; max-age=" + (60*60*24*7);
                document.cookie = "access_token=Bearer " + '{access_token}' + "; path=/; max-age=" + (60*60*24*7);
                
                // Redirect to the original URL
                window.location.href = '{from_url}';
            </script>
        </head>
        <body>
            <h2>Authentication Successful</h2>
            <p>Redirecting to application...</p>
        </body>
        </html>
        '''
        
        # Set cookies in the HTTP response as well
        response = HTMLResponse(content=html_content)
        
        # HTTP-only secure cookie (most secure)
        response.set_cookie(
            key="access_token", 
            value=f"Bearer {access_token}",
            httponly=True,
            samesite="lax",
            path="/",
            max_age=60*60*24*7  # 7 days
        )
        
        # JS-accessible token
        response.set_cookie(
            key="auth_token", 
            value=access_token,
            httponly=False,  # Make accessible to JavaScript
            samesite="lax",
            path="/",
            max_age=60*60*24*7  # 7 days
        )
        
        # Base token name
        response.set_cookie(
            key="token", 
            value=access_token,
            httponly=False,
            samesite="lax",
            path="/",
            max_age=60*60*24*7  # 7 days
        )
        
        # Authorization header for any fetch
        response.headers["Authorization"] = f"Bearer {access_token}"
        
        logger.info(f"Login successful for {form_data.username}, sending enhanced redirect page")
        return response
    
    logger.info(f"Returning token for {form_data.username} without redirect")
    return Token(access_token=access_token, token_type="bearer")

@router.post("/register", response_model=User)
def register(
        *, db: Session = Depends(deps.get_db), user_in: UserCreate
) -> User:
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
                "trial_period_days": 7,
                "metadata": {
                    "plan": checkout_request.plan,
                    "customer_name": checkout_request.name,
                    "company": checkout_request.company or "",
                },
            },
            success_url=checkout_request.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=checkout_request.cancel_url,
            allow_promotion_codes=True,
        )

        logger.info(f"Created checkout session {session.id} for {checkout_request.email}")

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

    # Verify webhook signature
    try:
        if settings.STRIPE_WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        else:
            # In development, parse without verification
            import json
            event = stripe.Event.construct_from(
                json.loads(payload), stripe.api_key
            )
    except ValueError as e:
        logger.error(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.SignatureVerificationError as e:
        logger.error(f"Invalid webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.type
    logger.info(f"Processing Stripe webhook: {event_type}")

    # Handle checkout.session.completed - create user account
    if event_type == "checkout.session.completed":
        session = event.data.object
        customer_id = session.customer
        subscription_id = session.subscription

        # Get customer details from Stripe
        try:
            customer = stripe.Customer.retrieve(customer_id)
        except stripe.StripeError as e:
            logger.error(f"Failed to retrieve Stripe customer {customer_id}: {e}")
            return {"status": "error", "message": "Failed to retrieve customer"}

        email = customer.email
        if not email:
            logger.error(f"Stripe customer {customer_id} has no email")
            return {"status": "error", "message": "Customer has no email"}

        name = customer.name or email.split("@")[0]
        company = customer.metadata.get("company", "") if customer.metadata else ""

        # Check if user already exists
        existing_user = crud.user.get_user_by_email(session=db, email=email)
        if existing_user:
            # Update existing user with subscription info
            existing_user.stripe_customer_id = customer_id
            existing_user.stripe_subscription_id = subscription_id
            db.add(existing_user)
            db.commit()
            logger.info(f"Updated existing user {email} with subscription {subscription_id}")
            return {"status": "success", "message": "User updated"}

        # Generate a secure random password
        temp_password = secrets.token_urlsafe(16)

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
            db.add(new_user)
            db.commit()
            logger.info(f"Created new user {email} from Stripe checkout")

            # TODO: Send welcome email with password reset link
            # For now, log the temp password (remove in production!)
            logger.info(f"User {email} created with temp password (send reset email)")

            return {"status": "success", "message": "User created", "user_id": str(new_user.id)}
        except Exception as e:
            logger.error(f"Failed to create user {email}: {e}")
            db.rollback()
            return {"status": "error", "message": str(e)}

    # Handle subscription deleted
    elif event_type == "customer.subscription.deleted":
        subscription = event.data.object
        customer_id = subscription.customer

        # Find user by stripe_customer_id and deactivate
        # This would require a query by stripe_customer_id
        logger.info(f"Subscription {subscription.id} deleted for customer {customer_id}")
        return {"status": "success", "message": "Subscription cancellation noted"}

    # Return success for unhandled events
    return {"status": "success", "message": f"Unhandled event type: {event_type}"}
