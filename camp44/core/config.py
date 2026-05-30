from typing import List, Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    API_V1_STR: str = "/api/v1"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access tokens
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    ALGORITHM: str = "HS256"
    DATABASE_URL: str = "postgresql://camp44:camp44@localhost:5432/camp44"
    # Connection-pool sizing + resilience (PostgreSQL only; ignored for sqlite).
    # Raises the bare SQLAlchemy 5+10 default and makes a connection stranded
    # mid-transaction self-heal instead of wedging the pool until a restart
    # (stress-test finding F3). Per-worker — keep
    # (DB_POOL_SIZE + DB_MAX_OVERFLOW) * uvicorn_workers under Postgres
    # max_connections.
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 10  # seconds to wait for a free connection
    DB_POOL_RECYCLE: int = 1800  # recycle connections after 30 min
    # Postgres server-side per-connection timeouts (milliseconds). The
    # idle-in-transaction timeout is the F3 fix: Postgres kills a connection
    # left mid-transaction so pool_pre_ping can recycle it. statement_timeout
    # defaults off to avoid surprising long-running admin/report queries.
    DB_IDLE_IN_TX_TIMEOUT_MS: int = 30000
    DB_STATEMENT_TIMEOUT_MS: int = 0  # 0 = disabled
    DB_CONNECT_TIMEOUT: int = 10  # seconds
    MINIO_URL: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minio"
    MINIO_SECRET_KEY: str = "minio123"
    JWT_SECRET_KEY: str = (
        "test_secret"  # Override via JWT_SECRET_KEY env var in production
    )
    JWT_ALGORITHM: str = "HS256"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    # OAuth/OIDC settings
    OAUTH_ENABLED: bool = False
    OIDC_ISSUER_URL: Optional[str] = None  # e.g. "https://accounts.google.com"
    OIDC_CLIENT_ID: Optional[str] = None
    OIDC_CLIENT_SECRET: Optional[str] = None
    OIDC_AUTHORIZATION_ENDPOINT: Optional[str] = (
        None  # e.g. "https://accounts.google.com/o/oauth2/auth"
    )
    OIDC_TOKEN_ENDPOINT: Optional[str] = (
        None  # e.g. "https://oauth2.googleapis.com/token"
    )
    OIDC_JWKS_URI: Optional[str] = (
        None  # e.g. "https://www.googleapis.com/oauth2/v3/certs"
    )
    OIDC_USERINFO_ENDPOINT: Optional[str] = (
        None  # e.g. "https://openidconnect.googleapis.com/v1/userinfo"
    )
    OIDC_TENANT_CLAIM: str = (
        "tenant_id"  # Claim name containing tenant_id in OIDC token
    )
    OIDC_CALLBACK_URL: Optional[str] = (
        None  # e.g. "http://localhost:8000/api/v1/auth/oidc/callback"
    )
    OIDC_SCOPES: List[str] = ["openid", "profile", "email"]

    # WebAuthn/Passkey settings
    WEBAUTHN_RP_ID: str = "localhost"  # Relying Party ID, typically your domain
    WEBAUTHN_RP_NAME: str = "Camp44"  # Relying Party name displayed to users
    WEBAUTHN_ORIGIN: str = "http://localhost:8000"  # Origin URL for WebAuthn requests
    WEBAUTHN_TIMEOUT: int = 60000  # Timeout in milliseconds

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_GROWTH_PRICE_ID: str = "price_1SzLgVClJjEKfkheqCiFKh6J"
    STRIPE_SCALE_PRICE_ID: str = "price_1SzLgVClJjEKfkhe7wWMfjvA"

    # Base44 Integration
    BASE44_API_URL: str = "https://app.base44.com/api"
    BASE44_API_KEY: Optional[str] = None
    BASE44_APP_ID: Optional[str] = None
    BASE44_AUTH_PROXY: bool = (
        False  # If True, proxy auth to Base44 instead of using local auth
    )

    # Frontend URL (for password reset emails etc.)
    FRONTEND_URL: Optional[str] = None

    # Feature Flags — disable Camp44 route groups not needed by the host app
    CAMP44_DISABLE_FUNCTIONS: bool = False
    CAMP44_DISABLE_METERING: bool = False
    CAMP44_DISABLE_DEMO_BOOKING: bool = False
    CAMP44_DISABLE_BASE44_PROXY: bool = False
    CAMP44_DISABLE_BULK: bool = False
    CAMP44_DISABLE_ADMIN: bool = False
    CAMP44_DISABLE_PASSKEY: bool = False
    CAMP44_DISABLE_OIDC: bool = False
    CAMP44_DISABLE_INTEGRATIONS: bool = False
    CAMP44_DISABLE_ENTITIES: bool = False
    CAMP44_DISABLE_PUBLIC: bool = False
    CAMP44_DISABLE_APPS: bool = False
    CAMP44_DISABLE_STRIPE: bool = False

    # Testing mode (set TESTING=1 to enable test-only behaviour)
    TESTING: bool = False

    # First Superuser
    FIRST_SUPERUSER: str = "admin@example.com"
    FIRST_SUPERUSER_PASSWORD: str = "password"

    # Domain-based auto-admin: comma-separated list of email domains
    ADMIN_EMAIL_DOMAINS: str = (
        "regression.io,taliertradinggroup.com,talliertradinggroup.com"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()

_INSECURE_JWT_SECRETS = {
    "test_secret",
    "dev-secret-change-in-production",
    "secret",
    "changeme",
    "",
}


def validate_production_settings():
    """
    Refuse to start with insecure defaults in any non-test environment.

    Previously this guard treated ``localhost`` in DATABASE_URL as proof of a
    dev environment and downgraded an insecure JWT_SECRET_KEY to a warning.
    That bypassed the check on real deployments that happen to reach Postgres
    via a sidecar / pgbouncer / kubectl port-forward on 127.0.0.1, leaving
    them booting with the literal ``"test_secret"`` and accepting forged
    JWTs. The exception is now scoped to test-only contexts: explicit
    ``TESTING=1`` or a sqlite DB URL. Everything else fails closed.
    See scalemate-service/docs/security/2026-05-24-audit.md P1-1.
    """
    import os
    import warnings

    is_test = os.environ.get("TESTING", "").lower() in (
        "1",
        "true",
        "yes",
    ) or settings.DATABASE_URL.startswith("sqlite")
    if settings.JWT_SECRET_KEY in _INSECURE_JWT_SECRETS:
        if is_test:
            warnings.warn(
                "JWT_SECRET_KEY is using an insecure default. "
                "Set it in .env for production.",
                stacklevel=2,
            )
        else:
            raise RuntimeError(
                "FATAL: JWT_SECRET_KEY is set to an insecure default "
                f"({settings.JWT_SECRET_KEY!r}). Set a strong, unique "
                "JWT_SECRET_KEY in your .env file. "
                "(Set TESTING=1 or use a sqlite:// DATABASE_URL to bypass "
                "this check in test environments.)"
            )
    if not is_test and settings.FIRST_SUPERUSER_PASSWORD == "password":
        raise RuntimeError(
            "FATAL: FIRST_SUPERUSER_PASSWORD is 'password'. "
            "Set a strong password in your .env file."
        )
