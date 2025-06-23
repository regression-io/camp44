from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from camp44.api.v1.endpoints import auth, users, apps, entities, bulk, integrations, functions, metering
from camp44.api.v1 import oidc, passkey
from camp44.db.session import create_db_and_tables
from camp44.db.initial_data import seed_initial_data
from camp44.core.errors import http_exception_handler, generic_exception_handler
from camp44.core.config import settings
from camp44.core.tracing import setup_tracer
from camp44.core.middleware import SecurityHeadersMiddleware
from camp44.middleware.tenant import TenantMiddleware
from camp44.middleware.tenant_oidc import OIDCTenantMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


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
    allow_origins=["*"],  # In production, you should restrict this to your frontend's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(users.router, prefix="/api/v1/users", tags=["users"])
app.include_router(apps.router, prefix="/api/v1/apps", tags=["apps"])
app.include_router(entities.router, prefix="/api/v1/apps/{app_id}/entities", tags=["entities"])
app.include_router(bulk.router, prefix="/api/v1/apps/{app_id}/bulk", tags=["bulk"])
app.include_router(integrations.router, prefix="/api/v1/apps/{app_id}/integrations", tags=["integrations"])
app.include_router(functions.router, prefix="/api/v1/functions", tags=["functions"])
app.include_router(metering.router, prefix="/api/v1/metering", tags=["metering"])

# OIDC and Passkey routers
app.include_router(oidc.router, prefix="/api/v1/auth/oidc", tags=["auth", "oidc"])
app.include_router(passkey.router, prefix="/api/v1/auth/passkey", tags=["auth", "passkey"])

FastAPIInstrumentor.instrument_app(app)

@app.get("/")
def read_root():
    """A simple endpoint to check if the service is running."""
    return {"message": "Welcome to Camp44"}

# Here we will later include routers for auth, entities, etc.
# from .auth import router as auth_router
# from .entities import router as entities_router
#
# app.include_router(auth_router, prefix="/auth", tags=["auth"])
# app.include_router(entities_router, prefix="/api/apps/{app_id}/entities", tags=["entities"])
