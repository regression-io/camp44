# Project Progress

This document tracks the implementation progress of the MyBase44 service against the PRD.

## Phase 1: Scaffolding & Core Services

- [x] **Project Structure**: Set up directories, `pyproject.toml`, and initial files.
- [x] **Docker Compose**: Create `docker-compose.yml` for Postgres, MinIO, and the app.
- [x] **FastAPI App**: Basic "Hello World" app setup in `main.py`.
- [x] **Configuration**: Settings management using Pydantic Settings.
- [x] **Database Connection**: Establish connection to Postgres with SQLModel.
- [x] **Initial Models**: Define `User` model.
- [x] **Alembic Migrations**: Set up Alembic for database schema migrations.

## Phase 2: Authentication

- [x] `POST /api/v1/auth/login`: User login and token generation.
- [x] `POST /api/v1/auth/register`: New user registration.
- [x] `GET /api/v1/users/me`: Retrieve current user's profile.
- [x] `PATCH /api/v1/users/me`: Update current user's profile.
- [x] JWT token generation and validation logic.
- [x] Password hashing.
- [x] Dependency injection for authenticated user.

## Phase 3: Entities CRUD

- [x] **App Entity**: Defined `App` model and relationship with `User`.
- [x] `POST /api/v1/apps/`: Create a new application.
- [x] `GET /api/v1/apps/`: List applications for the current user.
- [x] `GET /api/v1/apps/{id}`: Retrieve a specific application by ID.
- [x] **Generic Entity Model**: Defined `Entity` model with JSONB data field.
- [x] **Generic Entity CRUD**: Implemented CRUD operations for entities.
- [x] `POST /api/v1/apps/{app_id}/entities/{entity_name}` (Create)
- [x] `GET /api/v1/apps/{app_id}/entities/{entity_name}` (List)
- [x] `GET /api/v1/apps/{app_id}/entities/{entity_name}/{id}` (Retrieve)
- [x] `PATCH /api/v1/apps/{app_id}/entities/{entity_name}/{id}` (Update)
- [x] `DELETE /api/v1/apps/{app_id}/entities/{entity_name}/{id}` (Delete)
- [x] `POST /api/v1/apps/{app_id}/entities/{entity_name}/filter`
- [x] `POST /api/v1/apps/{app_id}/bulk`

## Phase 4: Integrations & File Uploads

- [x] `GET /api/v1/apps/{app_id}/integrations` (Discovery)
- [x] `POST /api/v1/apps/{app_id}/integrations/{pkg}/{fn}` (Invocation)
- [x] `POST /api/v1/apps/{app_id}/integrations/Core.UploadFile`
- [x] S3/MinIO client and upload logic.

## Phase 5: Backend Functions

- [x] Stub implementation for `POST /api/v1/functions/{name}`.
- [ ] (Stretch) Deno/Firecracker integration.

## Phase 7: Billing & Metering

- [x] **Metering Endpoint**: `POST /api/v1/meter` to emit usage events.
- [ ] **Idempotency**: Ensure events can be retried without duplication (re-implement for RabbitMQ).
- [x] **Buffer**: Integrate RabbitMQ as a message queue for events.
- [x] **Processing**: Create a background worker to process events from the queue.
- [x] **DB Schema**: Extend `User` and `App` models with Stripe-related fields.
- [ ] **Stripe Integration**: Connect to Stripe to report usage and manage billing.

## Phase 6: NFRs & Ops

- [x] **Error Handling**: Middleware for custom error format.
- [x] **Observability**: OpenTelemetry middleware setup.
- [x] **Security**: Add basic security headers.
- [x] **CI/CD**: GitHub Actions for linting, testing.
- [x] **Testing**: Pytest setup with initial contract tests.
- [x] **Documentation**: Update `README.md` and generate OpenAPI docs.
