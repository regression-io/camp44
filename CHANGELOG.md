# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Fixed
- **Admin user list 500 error**: `GET /api/admin/users` crashed with `ResponseValidationError` when users had `NULL` roles in DB. Added default `[]` to `UserRead.roles` schema field
- **OIDC callback error returns JSON instead of redirect**: When OIDC authentication failed, the callback returned a JSON error response to the browser, leaving users stranded on a raw JSON page. Now redirects back to the frontend login page with `?error=auth_failed` param
- **Token refresh datetime crash**: Fixed `TypeError: can't compare offset-naive and offset-aware datetimes` in `POST /auth/refresh` — DB-loaded naive datetimes now normalized to UTC-aware before expiry comparison
- **OIDC middleware noise**: Suppressed "Token validation error: unsupported_algorithm" log that fired for every request using HS256 (Camp44) JWT tokens. Only unexpected OIDC errors are now logged at debug level.
- **Unused import**: Removed unused `jwt` import from `camp44/core/oauth.py`

### Added
- **Token refresh & revocation**: Short-lived 15-min access tokens with `tv` (token_version) claim, 30-day rotated refresh tokens stored as SHA-256 hashes, per-user instant revocation via `User.token_version`, refresh token family reuse detection
  - `POST /auth/refresh` — exchange refresh token for new token pair (rotation)
  - `POST /auth/logout` — server-side refresh token revocation
  - `RefreshToken` model with family_id for reuse detection
  - Backward compatible: old tokens without `tv` claim default to `tv=0`

### Security
- **P0: Unauthenticated admin self-promotion via `/auth/register`** — `UserCreate` exposed a `roles` field that `crud.user.create_user` persisted verbatim, letting any unauthenticated client POST `{"roles":["admin"]}` and become admin in one request. Removed `roles` from `UserCreate`; `create_user` now hard-codes `roles=[]`; auto-promotion remains gated behind `_ensure_admin_role` at login time. Audit existing admins with:
  `SELECT id, email, created_at FROM users WHERE 'admin' = ANY(roles) AND oidc_sub IS NULL AND hashed_password IS NOT NULL` and prune anything that wasn't manually granted. See `scalemate-service/docs/security/2026-05-24-audit.md` P0-1.
- **JWT secret startup validation**: App refuses to start in production with insecure default JWT_SECRET_KEY; warns in dev/SQLite mode
- **Superuser seeding guard**: Skips creating default `admin@example.com`/`password` superuser when credentials are still defaults
- **OIDC from_url open redirect**: `from_url` parameter now validated via `_sanitize_redirect_url` before storing in session
- **OIDC callback error info leak**: Internal error details no longer returned to client; logged server-side instead
- **File upload hardening**: Added 50MB size limit and filename sanitization (path traversal prevention + UUID prefix) to `Core.UploadFile`
- **SQL injection fix in entity filter**: Filter keys are now validated against `^[a-zA-Z_][a-zA-Z0-9_]*$` regex; parameterized bind names prevent collision
- **Registration response_model leak**: Changed `response_model=User` to `response_model=UserRead` on register endpoint to prevent leaking `hashed_password`
- **XSS in login redirect**: Added `_sanitize_redirect_url()` with allowlisted hosts for `from_url` parameter
- **CORS hardened**: Replaced `allow_origins=["*"]` with explicit origin allowlist
- **Removed header logging**: Prevented JWT tokens from being logged in middleware
- **Password hashing**: Removed `sha256_crypt` from CryptContext, bcrypt-only now
- **DB session leak**: Fixed `next(deps.get_db())` in POST `/login` — generator cleanup never ran; replaced with `with Session(engine)` context manager

### Fixed
- **Demo booking data loss**: Demo bookings and availability config were stored in-memory module variables — all data lost on every restart. Migrated to persistent `DemoBooking` and `DemoAvailabilityConfig` database tables with proper SQLModel models
- **commit/flush in CRUD**: Changed `session.flush()` to `session.commit()` in all CRUD operations (user, app, entity). Previously, `close()` would roll back uncommitted changes
- **Passkey auth guard**: `authenticate()` now returns `None` for OIDC-only users with no `hashed_password` instead of crashing
- **Missing CRUD functions**: Added `update()` and `get_users_with_passkey()` to `crud/user.py` (required by passkey flows)
- **Deprecated datetime**: Replaced `datetime.utcnow()` with `datetime.now(timezone.utc)` in user and entity models
- **DB echo disabled**: Set `echo=False` in session.py to prevent SQL logging in production
- **Model imports for Alembic**: Ensured all models are imported in `models/__init__.py`

### Added
- **Admin API** (`/api/admin/*`) - Comprehensive admin endpoints for system management
  - `GET /api/admin/stats` - Dashboard statistics (users, apps, entities)
  - User management: list, get, update, activate, deactivate, make-admin, remove-admin, delete
  - App management: list all apps
  - Entity management: list types, list by type, delete
  - All endpoints require `is_superuser` privilege
- **Base44 Auth Proxy** - Optional mode to proxy authentication to Base44
  - `BASE44_AUTH_PROXY` config setting
  - `/api/base44/auth/login` - Redirect to Base44 login
  - `/api/base44/auth/me` - Proxy user info
  - `PATCH /api/base44/auth/me` - Proxy profile updates
- **Base44 Integration Proxy** - Proxy Core integrations to Base44
  - `/api/base44/invoke` - LLM requests
  - `/api/base44/send-email` - Email requests
  - `/api/base44/send-sms` - SMS requests
  - `/api/base44/generate-image` - Image generation
  - `/api/base44/extract-data` - File data extraction

### Fixed
- **Test paths** - Fixed all test files to use correct API routes (`/api/` instead of `/api/v1/`)
  - `tests/conftest.py`, `test_apps.py`, `test_entities.py`, `test_login.py`, `test_metering.py`
  - OIDC and passkey tests now use `/auth/oidc/` and `/auth/passkey/` (no `/api` prefix)
- **UUID type hints** - Fixed path parameters to use `uuid.UUID` instead of `str` in:
  - `apps.py` - `read_app()` endpoint
  - `entities.py` - `read_entity()`, `update_entity()`, `delete_entity()` endpoints
  - `deps.py` - `get_app_by_id_from_path()` dependency
  - CRUD layer (`app.py`, `entity.py`) - Now handles both UUID and string IDs
- **CI workflow** - Made tests blocking again now that paths are correct

### Changed
- Admin routes registered at both `/admin` and `/api/admin` for SDK compatibility

### Security
- Admin endpoints protected by `is_superuser` check
- Admins cannot deactivate or remove admin from themselves
- Admins cannot delete their own account
