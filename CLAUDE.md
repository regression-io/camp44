# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Camp44 is a self-hostable, open-source FastAPI backend that provides API compatibility with Base44 (Wix's backend service). It allows developers to run Base44-compatible frontends on their own infrastructure.

**Key Technologies:**
- FastAPI (synchronous endpoints with async lifespan)
- SQLModel + SQLAlchemy (PostgreSQL)
- Alembic (database migrations)
- uv (Python package manager)
- Docker Compose (local development)
- MinIO (S3-compatible storage)
- RabbitMQ (message queue for metering)
- Stripe (billing integration)

## Development Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip sync pyproject.toml --all-extras

# Start infrastructure services (Postgres, MinIO, RabbitMQ)
docker-compose up -d

# Run database migrations
uv run alembic upgrade head
```

### Running the Application
```bash
# Development mode with auto-reload
uv run uvicorn camp44.main:app --reload --host 0.0.0.0 --port 5050

# Run in Docker (full stack)
docker-compose up
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/api/test_auth.py

# Run with verbose output
uv run pytest -v

# Run with coverage
uv run pytest --cov=camp44
```

### Database Migrations
```bash
# Create new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Show migration history
uv run alembic history
```

### Code Quality
```bash
# Format code
uv run black camp44/

# Lint code
uv run ruff check camp44/

# Type checking
uv run mypy camp44/
```

## Architecture & Key Concepts

### Multi-Tenancy with Row-Level Security (RLS)

The application uses PostgreSQL Row-Level Security for tenant isolation:

1. **TenantMiddleware** (`camp44/middleware/tenant.py`): Extracts `tenant_id` from JWT token and stores it in `request.state.tenant_id`
2. **Database Layer**: Sets PostgreSQL session variable `app.tenant_id` for each request
3. **RLS Policies**: Automatically filter all queries by the session's tenant_id

**Important**: All data access is automatically scoped to the authenticated user's tenant. This happens at the database level, not in application code.

### Generic Entity System

Camp44 provides a schemaless entity storage system:

- **Entity Model** (`camp44/models/entity.py`): Each entity has a `name` (type) and `data` (JSONB field)
- **App-Scoped**: All entities belong to an `App`, owned by a `User`
- **Endpoints**: `/api/apps/{app_id}/entities/{entity_name}/*`
- **Filtering**: `POST /api/apps/{app_id}/entities/{entity_name}/filter` with JSON query syntax

This allows frontends to store arbitrary JSON data without defining schemas upfront.

### Synchronous API with Async Lifespan

**Critical**: The application uses **synchronous endpoints** but **async lifespan**:
- All route handlers are `def` functions (not `async def`)
- Database sessions use `Session` (not `AsyncSession`)
- FastAPI's lifespan context manager is `asynccontextmanager` (required by FastAPI)

When writing new endpoints, use synchronous functions.

### Authentication & Authorization

**Multiple Auth Methods**:
1. **JWT Bearer Tokens** (primary): Standard email/password login
2. **WebAuthn/Passkeys**: Passwordless authentication (`/auth/passkey/*`)
3. **OIDC**: OpenID Connect integration (`/auth/oidc/*`)

**Dependencies**:
- `get_current_user()`: Requires valid JWT token
- `get_current_active_user()`: Requires active user
- `get_app_by_id_from_path()`: Validates app ownership

**Token Claims**:
- `sub`: User ID (UUID)
- `tenant_id`: Tenant identifier for RLS

### File Uploads

Files are stored in MinIO (S3-compatible):
- Endpoint: `POST /api/apps/{app_id}/integrations/Core.UploadFile`
- Client: `camp44/core/s3.py`
- Bucket per app: Named after app ID

### Metering & Billing

**Architecture**:
1. Client sends usage events to `POST /api/metering`
2. Events are queued in RabbitMQ
3. Background worker (`camp44/workers/metering_processor.py`) processes events
4. Worker reports usage to Stripe

**Running Worker**:
```bash
python -m camp44.workers.metering_processor
```

### Bulk Operations

Atomic multi-entity operations via `POST /api/apps/{app_id}/bulk`:
```json
{
  "operations": [
    {"method": "create", "entity_name": "User", "data": {...}},
    {"method": "update", "entity_name": "Post", "id": "...", "data": {...}},
    {"method": "delete", "entity_name": "Comment", "id": "..."}
  ]
}
```

All operations succeed or all fail (transactional).

## Project Structure

```
camp44/
├── api/
│   ├── deps.py              # Dependency injection (auth, db)
│   └── v1/
│       ├── endpoints/       # Route handlers
│       │   ├── auth.py      # Login, register, login form
│       │   ├── users.py     # User profile management
│       │   ├── apps.py      # App CRUD
│       │   ├── entities.py  # Generic entity CRUD
│       │   ├── bulk.py      # Bulk operations
│       │   ├── integrations.py  # File uploads
│       │   ├── functions.py     # Server-side functions (stub)
│       │   └── metering.py      # Usage tracking
│       ├── oidc.py          # OpenID Connect auth
│       └── passkey.py       # WebAuthn/Passkey auth
├── core/
│   ├── config.py            # Settings (environment variables)
│   ├── security.py          # JWT, password hashing
│   ├── errors.py            # Exception handlers
│   ├── middleware.py        # Security headers
│   ├── tracing.py           # OpenTelemetry setup
│   ├── s3.py                # MinIO client
│   ├── oauth.py             # OAuth utilities
│   └── webauthn.py          # WebAuthn utilities
├── models/                  # SQLModel data models
│   ├── user.py
│   ├── app.py
│   ├── entity.py
│   ├── token.py
│   ├── metering.py
│   └── bulk.py
├── crud/                    # Database operations
│   ├── user.py
│   ├── app.py
│   └── entity.py
├── middleware/              # Request/response middleware
│   ├── tenant.py            # Extract tenant_id from JWT
│   └── tenant_oidc.py       # OIDC tenant extraction
├── db/
│   ├── session.py           # Database engine, session factory
│   └── initial_data.py      # Seed data (first superuser)
├── workers/
│   └── metering_processor.py  # Background worker for billing
├── integrations/            # External service integrations (stub)
└── main.py                  # FastAPI app initialization
```

## Database Models

### User
- `id` (UUID, primary key)
- `email` (unique)
- `hashed_password`
- `is_active` (boolean)
- `stripe_customer_id` (nullable)
- Relationships: `apps` (one-to-many)

### App
- `id` (UUID, primary key)
- `name`
- `description`
- `owner_id` (foreign key to User)
- `stripe_subscription_id` (nullable)
- Relationships: `owner` (User), `entities` (one-to-many)

### Entity
- `id` (UUID, primary key)
- `name` (entity type, e.g., "Post", "Comment")
- `data` (JSONB field - stores arbitrary JSON)
- `app_id` (foreign key to App)
- `created_at`, `updated_at`
- Relationships: `app` (App)

## API Routes

All routes are duplicated with and without `/api` prefix for SDK compatibility:
- `/auth/*` and `/api/auth/*`
- `/apps/*` and `/api/apps/*`
- etc.

**Special Route**: `/login` redirects to `/auth/login` for Base44 SDK compatibility.

## Environment Variables

Configure via `.env` file or environment variables:

**Database:**
- `DATABASE_URL`: PostgreSQL connection string (default: `sqlite:///./test.db`)

**Security:**
- `JWT_SECRET_KEY`: Secret for JWT signing (required)
- `JWT_ALGORITHM`: Algorithm for JWT (default: `HS256`)
- `ACCESS_TOKEN_EXPIRE_MINUTES`: Token expiration (default: 11520 = 8 days)

**MinIO/S3:**
- `MINIO_URL`: MinIO server URL (default: `localhost:9000`)
- `MINIO_ACCESS_KEY`: Access key
- `MINIO_SECRET_KEY`: Secret key

**RabbitMQ:**
- `RABBITMQ_URL`: AMQP connection string (default: `amqp://guest:guest@localhost:5672/`)

**Stripe:**
- `STRIPE_SECRET_KEY`: Stripe API key
- `STRIPE_WEBHOOK_SECRET`: Webhook signature secret

**OAuth/OIDC:**
- `OAUTH_ENABLED`: Enable OIDC (default: `false`)
- `OIDC_ISSUER_URL`: OIDC provider URL
- `OIDC_CLIENT_ID`: OAuth client ID
- `OIDC_CLIENT_SECRET`: OAuth client secret
- `OIDC_CALLBACK_URL`: Callback URL for OIDC flow

**WebAuthn:**
- `WEBAUTHN_RP_ID`: Relying Party ID (default: `localhost`)
- `WEBAUTHN_RP_NAME`: Relying Party name (default: `Camp44`)
- `WEBAUTHN_ORIGIN`: Origin URL (default: `http://localhost:8000`)

**Initialization:**
- `FIRST_SUPERUSER`: Initial admin email (default: `admin@example.com`)
- `FIRST_SUPERUSER_PASSWORD`: Initial admin password (default: `password`)

## Testing Notes

- Tests use SQLite (`test.db`) by default
- Fixed test user ID: `11111111-1111-1111-1111-111111111111`
- Most tests use real services (PostgreSQL, RabbitMQ) for functional testing
- Tests are synchronous to match API implementation
- OpenTelemetry is disabled in test mode (set `TESTING=1` env var)

## Known Issues & Workarounds

1. **bcrypt Compatibility**: Applied patch in `camp44/utils/bcrypt_fix.py` for passlib/bcrypt compatibility
2. **Package Lock**: Never commit `package-lock.json` or use `npm ci` (per project rules)
3. **Async Lifespan Required**: FastAPI requires async lifespan even with sync endpoints
4. **RLS Migrations**: Row-Level Security policies must be created manually in migrations

## Development Workflow

1. Make code changes
2. Run tests: `uv run pytest`
3. Update database schema: `uv run alembic revision --autogenerate -m "description"`
4. Apply migration: `uv run alembic upgrade head`
5. Update README.md and CHANGELOG.md before pushing (per project rules)
6. Commit with conventional commit format: `type(scope): description`

## API Documentation

Once running, interactive API docs available at:
- Swagger UI: http://localhost:5050/docs
- ReDoc: http://localhost:5050/redoc
