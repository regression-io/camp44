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
from camp44.db.session import engine
from camp44.main import app as fastapi_app
from camp44.models.app import App
from camp44.models.user import User
from camp44.core.security import create_access_token


# Set the TESTING environment variable to disable OpenTelemetry
# This must happen before any imports that might set up tracing
os.environ["TESTING"] = "1"


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
    print("\nTEST_APP FIXTURE - Creating test app")
    app_in = {
        "name": "Test App",
        "description": "App created for testing entities",
    }
    print(f"TEST_APP FIXTURE - Request payload: {app_in}")
    
    try:
        response = client.post(
            "/api/v1/apps/",
            json=app_in,
        )
        print(f"TEST_APP FIXTURE - Response status: {response.status_code}")
        print(f"TEST_APP FIXTURE - Response body: {response.text[:200]}")  # Truncate if too long
        
        assert response.status_code == 200, f"Failed to create test app: {response.text}"

        created_app = response.json()
        app_obj = App(**created_app)
        print(f"TEST_APP FIXTURE - Created app with ID: {app_obj.id}")
        yield app_obj
    except Exception as e:
        print(f"TEST_APP FIXTURE - Exception creating app: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        # Try to clean up regardless of errors
        try:
            if 'created_app' in locals():
                print(f"TEST_APP FIXTURE - Cleaning up app ID: {created_app['id']}")
                
                # Clean up the app and its entities
                cleanup_response = client.delete(f"/api/v1/apps/{created_app['id']}")
                print(f"TEST_APP FIXTURE - Cleanup status: {cleanup_response.status_code}")
                
                # If HTTP delete fails, try direct SQL deletion
                if cleanup_response.status_code != 200:
                    print(f"TEST_APP FIXTURE - HTTP delete failed with {cleanup_response.status_code}, attempting direct SQL deletion")
                    
                    # Use SQLAlchemy to delete entities and app
                    from sqlalchemy import text
                    
                    # Delete related entities first
                    db_session.execute(text(f"DELETE FROM entity WHERE app_id = '{created_app['id']}'"))
                    db_session.execute(text(f"DELETE FROM app WHERE id = '{created_app['id']}'"))
                    db_session.commit()
                    print("TEST_APP FIXTURE - Direct SQL deletion completed")
        except Exception as e:
            print(f"TEST_APP FIXTURE - Cleanup exception: {type(e).__name__}: {str(e)}")


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
