import uuid
from contextlib import contextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44.models.user import User
from camp44.models.app import App
from camp44.main import app
from camp44.api import deps as api_deps

# Explicitly cast app to FastAPI to help IDE recognize dependency_overrides
app = cast(FastAPI, app)


@contextmanager
def authenticated_client(client: TestClient, user: User):
    """Context manager that yields a TestClient with auth overridden for the given user."""
    # Create static reference to the user to ensure both sync and contexts
    # use the exact same user object
    def get_test_user():
        return user
    
    # Override both sync and authentication dependencies
    app.dependency_overrides[api_deps.get_current_active_user] = get_test_user
    try:
        yield client
    finally:
        app.dependency_overrides.pop(api_deps.get_current_active_user)


def test_create_list_get_app(client: TestClient, test_user: User):
    """Test the full CRUD workflow for apps as an authenticated user."""
    print(f"\nTEST USER DETAILS - ID: {test_user.id}, Email: {test_user.email}")
    
    # Confirm test user has our expected fixed UUID
    expected_id = uuid.UUID("11111111-1111-1111-1111-111111111111")
    assert test_user.id == expected_id, f"Test user ID mismatch: {test_user.id} != {expected_id}"
    
    with authenticated_client(client, test_user) as auth_client:
        # Create new app
        payload = {"name": "Test App", "description": "A test application"}
        print(f"Creating app with owner_id: {test_user.id}")
        
        create_response = auth_client.post("/api/apps/", json=payload)
        print(f"Create app response code: {create_response.status_code}")
        print(f"Create app response body: {create_response.text}")
        
        assert create_response.status_code == 200, create_response.text
        created = create_response.json()
        assert created["name"] == payload["name"]
        assert created["description"] == payload["description"]
        assert uuid.UUID(created["id"])  # Valid UUID
        app_id = created["id"]

        # List apps
        list_response = auth_client.get("/api/apps/")
        assert list_response.status_code == 200
        apps = list_response.json()
        assert len(apps) >= 1
        assert any(app["id"] == app_id for app in apps)

        # Get specific app
        get_response = auth_client.get(f"/api/apps/{app_id}")
        assert get_response.status_code == 200
        fetched = get_response.json()
        assert fetched == created


def test_create_app_unauthorized(unauthorized_client: TestClient):
    """Test that creating an app requires authentication."""
    payload = {"name": "Unauthorized App", "description": "Should fail"}
    response = unauthorized_client.post("/api/apps/", json=payload)
    assert response.status_code == 401
    error = response.json()
    # Handle either format: {'detail': '...'} or {'error': {'code': 401, 'message': '...'}}
    assert "detail" in error or ("error" in error and "code" in error["error"] and error["error"]["code"] == 401)
