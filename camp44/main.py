from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from camp44.api.v1 import oidc, passkey
from camp44.api.v1.endpoints import auth, users, apps, entities, bulk, integrations, functions, metering, base44_proxy, admin, demo_booking
from camp44.core.config import settings
from camp44.core.errors import http_exception_handler, generic_exception_handler
from camp44.core.middleware import SecurityHeadersMiddleware
from camp44.core.tracing import setup_tracer
from camp44.db.initial_data import seed_initial_data
from camp44.db.session import create_db_and_tables
from camp44.middleware.tenant import TenantMiddleware
from camp44.middleware.tenant_oidc import OIDCTenantMiddleware
from camp44.utils.bcrypt_fix import apply_bcrypt_patch

apply_bcrypt_patch()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Creating tables..")
    create_db_and_tables()
    seed_initial_data()
    setup_tracer()
    yield


app = FastAPI(
    lifespan=lifespan,
    exception_handlers={
        HTTPException: http_exception_handler,
        Exception: generic_exception_handler
    },
    title="Camp44",
    description="A FastAPI service to mirror and replace the Base44 cloud API.",
    version="0.1.0",
)

app.add_middleware(TenantMiddleware)
if settings.OAUTH_ENABLED:
    app.add_middleware(OIDCTenantMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.scalemate.regression.io",
        "https://gtm.scalemate.regression.io",
        "https://scalemate.regression.io",
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Original routes (without /api/ prefix)
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(apps.router, prefix="/apps", tags=["apps"])
app.include_router(entities.router, prefix="/apps/{app_id}/entities", tags=["entities"])
app.include_router(bulk.router, prefix="/apps/{app_id}/bulk", tags=["bulk"])
app.include_router(integrations.router, prefix="/apps/{app_id}/integrations", tags=["integrations"])
app.include_router(functions.router, prefix="/functions", tags=["functions"])
app.include_router(metering.router, prefix="/metering", tags=["metering"])
app.include_router(base44_proxy.router, prefix="/base44", tags=["base44-proxy"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(demo_booking.router, prefix="/demo", tags=["demo-booking"])

# OIDC and Passkey routers
# Note: oidc.router already has paths starting with /login, /callback, etc.
app.include_router(oidc.router, prefix="/auth/oidc", tags=["auth", "oidc"])
app.include_router(passkey.router, prefix="/auth/passkey", tags=["auth", "passkey"])

# Duplicate routes with /api/ prefix for SDK compatibility
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(apps.router, prefix="/api/apps", tags=["apps"])
app.include_router(entities.router, prefix="/api/apps/{app_id}/entities", tags=["entities"])
app.include_router(bulk.router, prefix="/api/apps/{app_id}/bulk", tags=["bulk"])
app.include_router(integrations.router, prefix="/api/apps/{app_id}/integrations", tags=["integrations"])
app.include_router(functions.router, prefix="/api/functions", tags=["functions"])
app.include_router(metering.router, prefix="/api/metering", tags=["metering"])
app.include_router(base44_proxy.router, prefix="/api/base44", tags=["base44-proxy"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(demo_booking.router, prefix="/api/demo", tags=["demo-booking"])

# Removed OpenTelemetry instrumentation

@app.get("/login")
async def redirect_login(request: Request):
    """
    Handle /login endpoint directly without redirects.
    The Base44 SDK uses this route for authentication.
    """
    # Instead of redirecting, serve the login form directly 
    # to prevent redirect loops
    from camp44.api.v1.endpoints.auth import login_page
    
    # Extract query parameters that the SDK might be sending
    from_url = request.query_params.get('from_url')
    app_id = request.query_params.get('app_id')
    
    # Call the login page handler directly
    return await login_page(request=request, from_url=from_url, app_id=app_id)

@app.post("/login")
async def handle_login(request: Request):
    """
    Handle POST requests to /login and forward them to the auth handler.
    """
    from camp44.api.v1.endpoints.auth import login
    from fastapi.security import OAuth2PasswordRequestForm
    from camp44.api import deps
    from camp44.db.session import engine
    from sqlmodel import Session

    form_data = await request.form()

    username = form_data.get("username", "")
    password = form_data.get("password", "")
    from_url = form_data.get("from_url", None)
    app_id = form_data.get("app_id", None)

    oauth_form = OAuth2PasswordRequestForm(username=username, password=password, scope="")

    with Session(engine) as db:
        return login(db=db, form_data=oauth_form, from_url=from_url, app_id=app_id, request=request)


@app.get("/")
def read_root():
    """A simple endpoint to check if the service is running."""
    return {"message": "Welcome to Camp44"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("camp44.main:app", host="0.0.0.0", port=8000, reload=True)
