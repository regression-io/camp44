from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
import logging
import json

from camp44 import crud
from camp44.api import deps
from camp44.core.security import create_access_token
from camp44.models.token import Token
from camp44.models.user import User, UserCreate

router = APIRouter()
logger = logging.getLogger(__name__)

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
