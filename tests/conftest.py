import os
import pathlib
import sys
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44.api import deps
from camp44.core.config import settings
from camp44.core.security import get_password_hash
from camp44.db.session import engine, create_db_and_tables
from camp44.main import app as fastapi_app
from camp44.models.app import App
from camp44.models.user import User
from camp44.core.security import create_access_token


# Set the TESTING environment variable to disable OpenTelemetry
# This must happen before any imports that might set up tracing
os.environ["TESTING"] = "1"


# Create database tables before any tests run
@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create database tables before running tests."""
    create_db_and_tables()
    yield


@pytest.fixture
def app() -> FastAPI:
    """Return FastAPI application for testing.

    This fixture returns the FastAPI application with proper test configuration.
    """
    return fastapi_app


@pytest.fixture
def db_session() -> Session:
    """Create a new database session for each test, wrapped in a transaction.

    This fixture provides an isolated database session for each test.
    """
    # Create a new database session connected to the test database
    with Session(engine) as session:
        yield session


@pytest.fixture
def client(app: FastAPI, db_session: Session) -> TestClient:
    """Return authenticated FastAPI test client.

    This fixture returns a TestClient that is authenticated as the test user.
    """
    # Override only the database dependency for consistent test data
    app.dependency_overrides[deps.get_db] = lambda: db_session

    # Create test user in the database
    user = User(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),  # Properly hash the test password
        is_active=True,
    )
    
    # Create or update the user in the database
    db_session.merge(user)
    db_session.commit()

    # Get authentication token for test user
    access_token = create_access_token(
        data={"sub": str(user.id)}
    )
    
    # Create a TestClient with the authentication token
    client = TestClient(app)
    client.headers = {"Authorization": f"Bearer {access_token}"}
    
    yield client

    app.dependency_overrides = {}


@pytest.fixture
def unauthorized_client(app: FastAPI, db_session: Session) -> TestClient:
    """Return unauthorized FastAPI test client for testing permission checks."""
    # Only override the database dependency
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

    # Cleanup
    try:
        cleanup_response = client.delete(f"/api/apps/{created_app['id']}")
        if cleanup_response.status_code != 200:
            from sqlalchemy import text
            db_session.execute(text(f"DELETE FROM entity WHERE app_id = '{created_app['id']}'"))
            db_session.execute(text(f"DELETE FROM app WHERE id = '{created_app['id']}'"))
            db_session.commit()
    except Exception:
        pass


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Return test user for testing.
    
    Always fetch the pre-created test user with fixed UUID.
    """
    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")  # Fixed test user UUID
    user = db_session.query(User).filter(User.id == user_id).first()
    if not user:
        raise ValueError("Test user not found. This should not happen as the client fixture creates the test user.")
    return user
