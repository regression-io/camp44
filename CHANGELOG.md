# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
