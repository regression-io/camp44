"""
Pytest configuration and fixtures for Camp44 tests.

Uses real Postgres for tests (same as production), with Alembic migrations
to create the schema. This catches model/migration mismatches before deploy.
"""

import os
import subprocess
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, create_engine, text

from camp44.api import deps
from camp44.core.security import create_access_token, get_password_hash
from camp44.models.app import App
from camp44.models.user import User

# Set the TESTING environment variable to disable OpenTelemetry
# This must happen before any imports that might set up tracing
os.environ["TESTING"] = "1"

# ---------------------------------------------------------------------------
# Database URL — use local Docker Postgres on port 5432
# ---------------------------------------------------------------------------
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://camp44:camp44@localhost:5432/camp44_test",
)

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _run_alembic_migrations(db_url: str) -> None:
    """Run alembic upgrade head against the test database."""
    env = {**os.environ, "DATABASE_URL": db_url}
    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Alembic migrations failed:\n{result.stderr}\n{result.stdout}"
        )


# ---------------------------------------------------------------------------
# Session-scoped: create/drop the test database once per run
# ---------------------------------------------------------------------------
@pytest.fixture(scope="session", autouse=True)
def test_engine():
    """
    Create a disposable camp44_test database on local Postgres.

    Schema is built via Alembic migrations (not create_all) so that
    model/migration mismatches are caught in tests, not production.
    """
    admin_url = TEST_DB_URL.rsplit("/", 1)[0] + "/postgres"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = 'camp44_test' AND pid <> pg_backend_pid()"
            )
        )
        conn.execute(text("DROP DATABASE IF EXISTS camp44_test"))
        conn.execute(text("CREATE DATABASE camp44_test"))

    _run_alembic_migrations(TEST_DB_URL)

    engine = create_engine(TEST_DB_URL)
    yield engine

    engine.dispose()
    with admin_engine.connect() as conn:
        conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = 'camp44_test' AND pid <> pg_backend_pid()"
            )
        )
        conn.execute(text("DROP DATABASE IF EXISTS camp44_test"))
    admin_engine.dispose()


@pytest.fixture
def app(test_engine) -> FastAPI:
    """Return FastAPI application for testing."""
    from camp44.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def db_session(test_engine) -> Session:
    """Create a new database session for each test."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture
def client(app: FastAPI, db_session: Session) -> TestClient:
    """Return authenticated FastAPI test client."""
    app.dependency_overrides[deps.get_db] = lambda: db_session

    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user = User(
        id=user_id,
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        is_active=True,
        tenant_id=str(user_id),
    )

    db_session.merge(user)
    db_session.commit()

    access_token = create_access_token(
        data={"sub": str(user.id), "tenant_id": str(user.id)}
    )

    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {access_token}"}

    yield client

    app.dependency_overrides = {}


@pytest.fixture
def unauthorized_client(app: FastAPI, db_session: Session) -> TestClient:
    """Return unauthorized FastAPI test client for testing permission checks."""
    app.dependency_overrides[deps.get_db] = lambda: db_session

    with TestClient(app) as c:
        yield c

    app.dependency_overrides = {}


@pytest.fixture
def test_app(client: TestClient, db_session: Session) -> App:
    """Create a test app for testing entities and other app-related endpoints."""
    app_in = {
        "name": "Test App",
        "description": "App created for testing entities",
    }

    response = client.post("/api/apps/", json=app_in)
    assert response.status_code == 200, f"Failed to create test app: {response.text}"

    created_app = response.json()
    app_obj = App(**created_app)
    yield app_obj

    try:
        cleanup_response = client.delete(f"/api/apps/{created_app['id']}")
        if cleanup_response.status_code != 200:
            from sqlalchemy import text as sa_text

            db_session.execute(
                sa_text(f"DELETE FROM entity WHERE app_id = '{created_app['id']}'")
            )
            db_session.execute(
                sa_text(f"DELETE FROM app WHERE id = '{created_app['id']}'")
            )
            db_session.commit()
    except Exception:
        pass


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Return test user for testing."""
    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    user = db_session.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError(
            "Test user not found. The client fixture creates the test user."
        )
    return user
