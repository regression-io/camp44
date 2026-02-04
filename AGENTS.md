# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Camp44 is a self-hostable, open-source FastAPI service providing a Base44-compatible API. It's a multi-tenant backend with JWT/OIDC/WebAuthn authentication, schemaless entity storage, file uploads to MinIO S3, usage metering with RabbitMQ, and row-level security (RLS) via PostgreSQL tenant isolation.

## Essential Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip sync pyproject.toml --all-extras
```

### Development Environment
```bash
# Start all services (Postgres, MinIO, RabbitMQ, FastAPI app, metering worker)
docker-compose up -d

# Start only dependencies (without the app)
docker-compose up -d db minio rabbitmq

# Run database migrations
uv run alembic upgrade head

# Run the application locally
uv run uvicorn camp44.main:app --reload --host 0.0.0.0 --port 5050
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/api/v1/test_login.py -v

# Run tests in recommended order (authentication → apps → entities → metering)
uv run pytest tests/api/v1/test_login.py tests/api/v1/test_oidc.py tests/api/v1/test_passkey.py tests/api/v1/test_apps.py tests/api/v1/test_entities.py tests/api/v1/test_metering.py -v
```

### Code Quality
```bash
# Run linting with ruff
uv run ruff check camp44/

# Run code formatting with black
uv run black camp44/

# Run type checking with mypy
uv run mypy camp44/
```

### Database Operations
```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description_of_changes"

# Apply migrations
uv run alembic upgrade head

# Rollback migration
uv run alembic downgrade -1

# View migration history
uv run alembic history
```

### Docker Operations
```bash
# View logs for all services
docker-compose logs -f

# View logs for specific service
docker-compose logs -f app

# Restart a specific service
docker-compose restart app

# Stop all services
docker-compose down

# Stop all services and remove volumes (destructive)
docker-compose down -v
```

## Architecture

### Multi-tenancy & Row-Level Security (RLS)
The application uses PostgreSQL RLS for tenant isolation:
- **TenantMiddleware** (`camp44/middleware/tenant.py`) extracts `tenant_id` from JWT tokens and stores it in `request.state.tenant_id`
- **OIDCTenantMiddleware** (`camp44/middleware/tenant_oidc.py`) handles tenant extraction from OIDC tokens
- Database session sets `app.tenant_id` PostgreSQL variable for RLS policies
- RLS policies are defined in migration `f5ff3b3c6d4e_enable_rls_and_tenant_policies.py`

### Authentication System
Three authentication methods are supported (see `docs/Authentication.md` for details):

1. **JWT Authentication** (`camp44/api/v1/endpoints/auth.py`)
   - Traditional username/password flow
   - Tokens include `tenant_id` claim for RLS

2. **OIDC/OAuth** (`camp44/api/v1/oidc.py`)
   - External identity provider integration (Google, Auth0, etc.)
   - Configurable via `OIDC_*` environment variables
   - Tenant ID extracted from configurable OIDC claim

3. **WebAuthn/Passkey** (`camp44/api/v1/passkey.py`)
   - Passwordless authentication using platform authenticators
   - Registration requires prior JWT/OIDC authentication
   - WebAuthn library handles credential verification

### API Structure
- **API versioning**: Routes available at both `/api/v1/*` and `/v1/*` (Base44 SDK compatibility)
- **Main router**: `camp44/main.py` assembles all endpoint routers
- **Endpoints**: `camp44/api/v1/endpoints/`
  - `auth.py` - JWT login/registration
  - `users.py` - User profile management
  - `apps.py` - Application CRUD
  - `entities.py` - Generic schemaless entity CRUD per app
  - `bulk.py` - Atomic multi-operation transactions
  - `integrations.py` - File upload to MinIO (Core.UploadFile)
  - `functions.py` - Server-side function stubs (extensibility)
  - `metering.py` - Usage tracking and Stripe integration

### Data Layer
- **Models**: `camp44/models/` - SQLModel definitions (User, App, Entity, etc.)
- **CRUD**: `camp44/crud/` - Database operations layer
- **Session management**: `camp44/db/session.py` - SQLModel engine and session factory
- **Migrations**: `migrations/versions/` - Alembic schema versioning
- **Entity model**: Schemaless JSON data storage (`entity.data` is a JSONB column)

### Background Processing
- **Metering worker**: `camp44/workers/metering_processor.py` - Consumes metering events from RabbitMQ
- **Queue system**: RabbitMQ for async metering event processing
- **Stripe integration**: Usage-based billing events sent to Stripe

### Middleware & Security
- **CORS**: Configured in `main.py` (set to `*` in dev, restrict in production)
- **Security headers**: `camp44/middleware/SecurityHeadersMiddleware`
- **OpenTelemetry**: Request tracing setup in `camp44/core/tracing.py`
- **Error handling**: Centralized handlers in `camp44/core/errors.py`

### Configuration
- **Settings**: `camp44/core/config.py` - Pydantic settings from environment variables
- **Environment file**: `.env` (not tracked, see `.env.example` if available)
- **Key settings**:
  - `DATABASE_URL` - PostgreSQL connection string
  - `MINIO_URL`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` - S3-compatible storage
  - `JWT_SECRET_KEY` - Token signing (MUST change in production)
  - `RABBITMQ_URL` - Message queue connection
  - `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` - Payment integration
  - `OAUTH_ENABLED`, `OIDC_*` - OIDC provider configuration
  - `WEBAUTHN_*` - Passkey authentication settings

## Development Practices

### Database Workflow
When modifying models:
1. Update the SQLModel class in `camp44/models/`
2. Generate migration: `uv run alembic revision --autogenerate -m "description"`
3. Review the generated migration file in `migrations/versions/`
4. Apply migration: `uv run alembic upgrade head`
5. Test with migrations applied to both SQLite (tests) and PostgreSQL (dev)

### Testing Strategy
- Tests use **SQLite** (`test.db`) with fixtures in `tests/conftest.py`
- The `client` fixture provides an authenticated TestClient with a pre-created test user
- The `test_app` fixture creates an app for entity testing and auto-cleans up
- Tests are **synchronous** (no async/await) matching the synchronous API implementation
- Run authentication tests first, as they establish the foundation for other tests

### Adding New API Endpoints
1. Create endpoint in `camp44/api/v1/endpoints/`
2. Define request/response models in `camp44/models/`
3. Add CRUD operations in `camp44/crud/` if needed
4. Register router in `camp44/main.py` with both `/api/v1/` and `/v1/` prefixes
5. Add tests in `tests/api/v1/`
6. Update API documentation (OpenAPI auto-generated at `/docs`)

### MinIO File Upload Pattern
Files are uploaded via `/api/v1/apps/{app_id}/integrations/Core.UploadFile`:
- Files stored in MinIO with app-scoped buckets
- Returns presigned URLs for client access
- Check `camp44/api/v1/endpoints/integrations.py` for implementation

### Bulk Operations
The `/api/v1/apps/{app_id}/bulk` endpoint supports atomic multi-entity operations:
- Create, update, delete multiple entities in a single transaction
- All operations succeed or fail together
- Useful for batch imports or complex data migrations

## API Access
- **Local development**: http://localhost:5050
- **Docker environment**: http://localhost:8000
- **Swagger UI**: http://localhost:5050/docs (or :8000/docs in Docker)
- **Default superuser**: admin@example.com / password (configure via `FIRST_SUPERUSER*` env vars)

## External Services
- **PostgreSQL**: Port 5432 (user: camp44, db: camp44)
- **MinIO Console**: http://localhost:9001 (minioadmin/minioadmin)
- **MinIO API**: http://localhost:9000
- **RabbitMQ Management**: http://localhost:15672 (guest/guest)
- **RabbitMQ AMQP**: Port 5672

## Common Issues

### Database Connection Errors
- Ensure PostgreSQL is running: `docker-compose up -d db`
- Check `DATABASE_URL` environment variable matches docker-compose settings
- For local dev: Use `postgresql://camp44:camp44@localhost:5432/camp44`
- For Docker: Use `postgresql://camp44:camp44@db:5432/camp44`

### Test Database Issues
- Tests use SQLite by default (`test.db`)
- Delete `camp44/test.db` if tests fail with schema errors
- Run migrations on test database if needed

### MinIO Connection Errors
- Ensure MinIO is running: `docker-compose up -d minio`
- Default credentials: `minioadmin`/`minioadmin` (change in production)
- Check `MINIO_URL` matches your environment (localhost:9000 for local, minio:9000 for Docker)

### RabbitMQ/Metering Worker Issues
- Verify RabbitMQ is running: `docker-compose up -d rabbitmq`
- Check worker logs: `docker-compose logs -f metering_worker`
- Management UI at http://localhost:15672 shows queue status

### OIDC/OAuth Configuration
- Requires `OAUTH_ENABLED=true` in environment
- All `OIDC_*` variables must be configured for external provider
- Callback URL must match provider configuration and `OIDC_CALLBACK_URL`
- Check `docs/Authentication.md` for provider-specific setup

## Code Quality Standards
- **Line length**: 88 characters (Black default)
- **Import sorting**: Ruff handles import organization
- **Type hints**: MyPy strict mode enabled - add type hints to all functions
- **Docstrings**: Required for public functions (enforced by Ruff, except D100/D104/D105/D107/D203/D212/D415)
- **Linting**: Ruff checks for code quality (E, F, I, W, C90, N, D rule sets)
