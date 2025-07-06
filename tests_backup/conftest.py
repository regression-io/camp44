import sys
import pathlib
# Ensure project root is on PYTHONPATH when running tests directly without installation.
sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))
import pytest
import os
import sys
from typing import Generator
import uuid
import datetime
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel
from sqlalchemy.sql import text
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from camp44.api import deps
from camp44.db.session import engine
from camp44.models import User, App
from camp44.core.security import get_password_hash


@pytest.fixture(scope="session", autouse=True)
def setup_test_user():
    """Create test user that will be visible across all database sessions.
    
    This fixture runs once per test session and creates a test user with a fixed UUID
    that will be reused across all tests. This ensures that the user is always present
    in the database before any tests run.
    """
    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")  # Fixed test user UUID
    email = "test@example.com"
    password = "testpassword"
    hashed_password = get_password_hash(password)
    
    # Clean up any existing user with this ID to avoid conflicts
    with engine.connect() as connection:
        connection.execute(text("DELETE FROM app WHERE owner_id = :user_id"), {"user_id": user_id})
        connection.execute(text("DELETE FROM \"user\" WHERE id = :user_id"), {"user_id": user_id})
        connection.commit()
        
        # Create user with all required fields using direct SQL
        # This ensures maximum compatibility across all sessions
        now = datetime.datetime.now(datetime.UTC)  # Use UTC timezone-aware datetime
        connection.execute(
            text("""
            INSERT INTO \"user\" (id, email, hashed_password, is_active, created_at, updated_at, roles, 
                            oidc_email_verified, oidc_sub, oidc_issuer, tenant_id, passkey_credentials) 
            VALUES (:id, :email, :hashed_password, :is_active, :created_at, :updated_at, '[]'::jsonb, 
                    :oidc_email_verified, :oidc_sub, :oidc_issuer, :tenant_id, '[]'::jsonb)
            """),
            {
                "id": user_id,
                "email": email,
                "hashed_password": hashed_password,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
                "oidc_email_verified": False,  # Required field
                "oidc_sub": None,              # Optional
                "oidc_issuer": None,           # Optional
                "tenant_id": None              # Optional
            }
        )
        connection.commit()


@pytest.fixture
def app() -> FastAPI:
    """Return FastAPI application for testing.
    
    This fixture returns the FastAPI application with proper test configuration.
    """
    from camp44.main import app
    return app


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """Create a new database session for each test, wrapped in a transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def client(app: FastAPI, db_session: Session) -> Generator:
    """Return authenticated FastAPI test client.
    
    This fixture returns a TestClient that is authenticated as the test user.
    """
    # This is to ensure we use the same session in tests
    # that is used during dependency overriding.
    app.dependency_overrides[deps.get_db] = lambda: db_session
    
    def override_get_current_user():
        return test_user(db_session)

    # Override app_id path parameter dependency for entity endpoints
    def override_get_app_by_id_from_path(app_id: str, session=None, current_user=None):
        # For testing, we'll create or get the test app by ID
        # This allows the path param extraction to work properly
        # We can safely ignore the session and current_user since we're mocking them
        from camp44 import crud
        test_app_obj = crud.app.get_app(db_session, id=app_id)
        if not test_app_obj:
            # If app ID doesn't exist, log for debugging
            print(f"Warning: App ID {app_id} not found during test, returning None")
        return test_app_obj
    
    # Override dependencies for testing
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_app_by_id_from_path] = override_get_app_by_id_from_path
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides = {}


@pytest.fixture
def unauthorized_client(app: FastAPI, db_session: Session) -> Generator:
    """Return unauthorized FastAPI test client for testing permission checks."""
    # Only override the database dependency, not the auth dependency
    app.dependency_overrides[deps.get_db] = lambda: db_session
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides = {}


@pytest.fixture
def test_app(client: TestClient) -> App:
    """Create a test app for testing entities and other app-related endpoints."""
    app_in = {
        "name": "Test App",
        "description": "App created for testing entities",
    }
    response = client.post(
        "/api/v1/apps/",
        json=app_in,
    )
    assert response.status_code == 200, f"Failed to create test app: {response.text}"
    
    created_app = response.json()
    app_obj = App(**created_app)
    yield app_obj
    
    # Clean up the app after the test
    response = client.delete(f"/api/v1/apps/{created_app['id']}")
    assert response.status_code == 200, f"Failed to delete test app: {response.text}"


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    # Always fetch the pre-created test user with fixed UUID
    user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")  # Fixed test user UUID
    
    # Directly fetch the user using its ID since we created it in setup
    # This ensures maximum compatibility between sync and sessions
    user = db_session.get(User, user_id)
    
    if not user:
        # If the user somehow doesn't exist, raise a clear error
        # Check if any users exist in the database for debugging
        result = db_session.execute(text('SELECT COUNT(*) FROM "user"'))
        user_count = result.scalar()
        
        # Try finding our test user specifically
        email_check = db_session.execute(
            text('SELECT id FROM "user" WHERE email = :email'), 
            {"email": "test@example.com"}
        )
        email_result = email_check.fetchone()
        
        error_msg = f"Test user with ID {user_id} not found in database. "
        error_msg += f"Total users in DB: {user_count}. "
        if email_result:
            error_msg += f"User with test email exists but has different ID: {email_result.id}"
        else:
            error_msg += "No user with test email found."
        
        raise Exception(error_msg)
    
    print(f"Using test user - ID: {user.id}, Email: {user.email}")
    return user
