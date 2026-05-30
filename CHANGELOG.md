# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed
- **Rate limiter can use Redis storage** (stress-test F3 deep-fix, step 2 prerequisite for multiple workers). `Limiter` now takes `storage_uri=settings.REDIS_URL or "memory://"` and `swallow_errors=True`. With `REDIS_URL` set, per-IP limits are shared across uvicorn workers/replicas (without it the in-memory store would give each worker its own counter = N× the real limit); `swallow_errors` makes the limiter **fail open** if Redis is unreachable so a cache outage can't lock everyone out of auth. New `REDIS_URL` setting; `redis>=5.0` dependency added. Unset → in-memory (unchanged for single-worker/dev/tests). Rate-limit + db suites pass.

### Security
- **Pin the security floors that were only holding by drift** (follow-up to F5; closes its deferred `starlette`/`fastapi` item). The build has no lockfile and every dep was an open `>=`, so a fresh image resolves *latest* — which is why prod already runs **fastapi 0.136.3 / starlette 1.2.0 / authlib 1.7.2 / python-multipart 0.0.29** and `pip-audit` on a fresh resolve is **clean**. The "major starlette 0.x→1.x bump" was therefore already live and healthy, but **accidental**: a resolver picking an older fastapi would silently un-bump starlette below its CVE fix. Codified the floors in `dependencies` so the patched state can't regress — `fastapi>=0.135.0` (drops the `starlette<1.0` cap), `starlette>=1.0.1` (PYSEC-2026-161), `authlib>=1.6.11`, `python-multipart>=0.0.27`. Direct starlette use is only stable middleware imports (`BaseHTTPMiddleware`, `Request/Response`, `SessionMiddleware`, `ASGIApp`, `types`), unchanged across 1.0. **Fixed the dead cbor2 cap:** the F5 `[tool.uv] constraint-dependencies = ["cbor2<6"]` never took effect because both Dockerfiles install with **pip**, which ignores `[tool.uv]` — prod has run **cbor2 6.1.1** all along. Removed the misleading constraint and added an honest `cbor2>=5.9.0` (no upper cap) to `dependencies`; the WebAuthn passkey *registration* path verified working on 6.x. **Deferred (own follow-ups):** migrate `camp44/core/oauth.py` off the deprecated `authlib.jose`→`joserfc` before authlib 2.0 (works on 1.7.x, deprecation warning only); and a fuller passkey *attestation-verification* smoke on cbor2 6.x.
- **Dependency CVE bumps** (stress-test finding F5; `pip-audit`). Updated the lock for known-CVE leaf libraries — **authlib 1.6.0→1.7.2 (7 CVEs, OIDC)**, **cryptography 45.0.4→48.0.0 (3)**, **python-multipart 0.0.20→0.0.29 (3, multipart/upload DoS)**, **urllib3 2.5.0→2.7.0 (3)**, **pyopenssl 25.1.0→26.2.0 (2)**, **pyasn1 0.6.1→0.6.3 (2)**, **cbor2 5.6.5→5.9.0 (2)** *(correction: the intended `<6` cap via `[tool.uv] constraint-dependencies` never applied — pip ignores `[tool.uv]`, so prod actually ran cbor2 6.x; see the floors-pinning entry above)*, **ecdsa→0.19.2**, **idna→3.17**, **requests→2.34.2**, **mako→1.3.12**, **pygments→2.20.0**, **python-dotenv→1.2.2**. `pip-audit` now reports clean for all of these. App imports and the `rate_limit`/`db` unit suites pass. **Deferred (separate PR, needs full validation):** `starlette` (3 CVEs) requires a `fastapi`+`starlette` major bump (0.46→1.x); and `authlib.jose` is deprecated in 1.7 (migrate `camp44/core/oauth.py` to `joserfc` before authlib 2.0). **CI must run the full suite; manual auth/OIDC/passkey/upload smoke recommended before merge.**
- **P1-7 follow-up: `localhost` redirect now dev-only** (Codex review 2026-05-28). `_ALLOWED_REDIRECT_HOSTS` previously allowed `localhost` in production, where a network-local attacker on the victim's machine could stand up a loopback listener and capture the post-login auth code via `?from_url=http://localhost:9999/...`. `localhost` and `127.0.0.1` now only pass `_sanitize_redirect_url` when `_is_dev_environment()` is true (`TESTING=1` or sqlite DB). Production deploys reject loopback redirects entirely. Test added.
- **P1-7 login no longer HTML-interpolates `from_url` into a meta-refresh**: `POST /auth/login` now returns `303 See Other` via `RedirectResponse` instead of an HTML page with `<meta http-equiv="refresh" content="0;url={from_url}">`. The host allowlist in `_sanitize_redirect_url` is unchanged, but a future sanitizer bypass would now only be an open-redirect (still bad, but bounded) instead of arbitrary HTML injection. Test at `tests/rate_limit/test_login_redirect.py`. See `scalemate-service/docs/security/2026-05-24-audit.md` §P1-7.
- **P1-4 rate limiting on auth surfaces** (`slowapi`): `POST /auth/login` 10/min/IP, `POST /auth/forgot-password` 5/min/IP, `POST /auth/set-password` 10/min/IP, `POST /auth/passkey/authenticate/options` 10/min/IP, `POST /auth/passkey/authenticate/verify` 10/min/IP. Anonymous brute-force, password-reset enumeration, and passkey-authentication-options enumeration are now bounded. Limiter is in-memory (single-replica deploys) and disabled when `TESTING=1` so the test suite isn't rate-limited. New tests in `tests/rate_limit/` (isolated from the broken parent DB autouse fixture). Body-param `request: SomeModel` renamed to `body: SomeModel` on the decorated handlers so the slowapi-required `request: Request` (FastAPI) parameter doesn't collide — internal-only, no API contract change. Composite IP+email keys and limits on the auth-required passkey `/register/*` endpoints are deferred follow-ups. See `scalemate-service/docs/security/2026-05-24-audit.md` §P1-4 and `scalemate-service/docs/bugs/P1-4/diagnosis.md`.

### Fixed
- **CRITICAL: successful password login returned 500** (stress-test finding F1). The P1-4 limiter was created with `headers_enabled=True`, but slowapi's `X-RateLimit-*` header injection requires every decorated route to expose a `response: Response` param (or return a `Response`). The sync auth handlers return Pydantic models (`POST /auth/login` → `Token`), so `_inject_headers` raised `parameter 'response' must be an instance of starlette.responses.Response` on the **success** path — every successful password login 500'd with no token, while invalid-credential calls (401 before that point) looked fine, hiding the outage. Confirmed live on production. Fix: `headers_enabled=False` (covers all `@limiter.limit` handlers: login, set-password, forgot-password, passkey×2, invite×2). Rate-limit **enforcement (429) is unaffected**. Regression test `tests/rate_limit/test_limiter_no_500_on_success.py`. To restore rate-limit headers later, add `response: Response` to each decorated handler first.
- **CRITICAL: connection-pool wedge under load** (stress-test finding F3). The sync engine used `create_engine(DATABASE_URL)` with SQLAlchemy's bare 5+10 pool and no resilience. Under load, connections were left stranded `idle in transaction` and never returned — once 15 leaked, every request waited 30 s for a connection then failed, and the pool **stayed wedged after load stopped until the container was restarted** (a staging ramp tipped from 0% to 100% errors at ~58 concurrent users). Root cause is pool/leak-bound, not RAM/CPU, so it applies to production. Fix in `camp44/db/session.py`: explicit `pool_size`/`max_overflow`/`pool_timeout`/`pool_recycle` + `pool_pre_ping`, and a Postgres server-side `idle_in_transaction_session_timeout` so a stranded connection is killed and recycled — the pool **self-heals** instead of wedging. All tunable via new `DB_*` settings (`config.py`); sqlite test path unchanged. Tests in `tests/db/test_engine_pool.py`. Follow-ups: run uvicorn with multiple workers (keep `(pool_size+overflow)*workers < max_connections`), cache the 1.5–2 s `/prospects/stats` & `/pipeline/stats` aggregations, and root-cause why sessions strand mid-transaction under concurrency (this change neutralises the impact; the residual leak source is worth eliminating).
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

### Removed
- **Dead unauthenticated routes (493 LOC out)** — three route groups had zero callers in the only live consumer (scalemate-service) and have been deleted. Pre-deletion code preserved at branch `archive/unused-public-routes-2026-05-24` (HEAD = `ac90c04`).
  - `POST /auth/checkout` + `CheckoutRequest`/`CheckoutResponse`/`get_plan_prices` (auth.py, ~120 LOC). Stripe checkout-session creator with implicit user creation. No frontend call sites in scalemate-ai-local or scalemate-gtm-local. scalemate-service runs subscription flows through `/users/me/subscribe` / `/users/me/billing-portal` instead.
  - `GET /demo/slots` + `POST /demo/book` + `BookDemoRequest`/`BookDemoResponse`/`AvailableSlotsResponse`/`TimeSlot` + `generate_time_slots` + `send_demo_booking_email` (demo_booking.py, ~208 LOC). Public demo-booking surface that no frontend exposes — only the `/admin/*` sub-routes are used by `AdminDemoAvailability.jsx`. Mootes audit P2-13 (email-body f-string concatenation into sales inbox); the vulnerable `send_demo_booking_email` is now gone. Admin endpoints unchanged.
  - `GET /base44/auth/login` + `GET /base44/auth/me` + `PATCH /base44/auth/me` (base44_proxy.py, ~150 LOC). Auth-proxy shims that always 404'd because `BASE44_AUTH_PROXY` was never enabled. `/invoke`, `/send-email`, `/send-sms`, `/generate-image`, `/extract-data` are unchanged — scalemate-ai-local's `invokeLLM` path still flows through them.
- `send_welcome_email` and `login_page` (both imported by scalemate-service) confirmed intact post-deletion.

### Security
- **P1: Passkey challenge store hardened** — replaced the bare module-level `_CHALLENGES = {}` dict (no TTL, no single-use, shared `"public"` slot across all concurrent discoverable ceremonies) with a thread-safe `_ChallengeStore`. Adds: 5-minute TTL, atomic single-use pop, `threading.Lock` around every map access, per-challenge-value keying for discoverable auth (eliminates the prior race where two concurrent passwordless logins overwrote each other's challenges). Verified across 8 unit tests including a 20-thread concurrent-pop test confirming exactly-one-winner semantics. Caveat: this is still an in-process store — multi-worker / multi-replica camp44 deployments must pin sessions to one worker, run a single worker, or replace the store with a shared backend (scalemate-service does the latter and is unaffected since it does not register camp44's passkey router). See `scalemate-service/docs/security/2026-05-24-audit.md` P1-2.
- **P1: Admin-domain auto-promotion now requires verified email** — `_ensure_admin_role` previously treated `hashed_password IS NOT NULL` as proof of email ownership and would auto-promote any password-signup user whose email matched `ADMIN_EMAIL_DOMAINS` on first login. That is not proof of ownership — an attacker registers as `admin@<our-domain>`, sets a password, logs in, and becomes admin. The check now requires `oidc_email_verified` (only IdP-confirmed emails qualify). Existing password admins are unaffected — the function only adds the role when absent. To grant admin to a password user, use the explicit `/admin/users/{id}/promote` endpoint. See `scalemate-service/docs/security/2026-05-24-audit.md` P1-6.
- **P1: JWT secret guard tightened** — `validate_production_settings()` previously downgraded an insecure default `JWT_SECRET_KEY` to a warning whenever `DATABASE_URL` contained `localhost`, on the assumption that meant "dev environment." Real deployments that reach Postgres via a sidecar / pgbouncer / kubectl port-forward on `127.0.0.1` matched that test and silently booted with the literal `"test_secret"`. The exception is now scoped to explicit test contexts only: `TESTING=1` env var or a `sqlite://` DATABASE_URL. Everything else fails closed with a fatal `RuntimeError`. See `scalemate-service/docs/security/2026-05-24-audit.md` P1-1.
- **P1: Refresh-token rotation TOCTOU race** — `/auth/refresh` previously did SELECT → check `is_revoked=False` → UPDATE in three separate steps, so two concurrent refreshes holding the same raw token could both see it unrevoked and both mint a replacement pair, defeating family reuse-detection. Replaced with an atomic `UPDATE refresh_tokens SET is_revoked=true WHERE token_hash=? AND is_revoked=false RETURNING *` (`crud.refresh_token.consume`). Of N concurrent callers, exactly one wins the UPDATE; the rest fall into the reuse-detection branch which revokes the family — which is the right outcome when a stolen token races a legitimate one. Works on both PostgreSQL and SQLite. See `scalemate-service/docs/security/2026-05-24-audit.md` P1-3.
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
