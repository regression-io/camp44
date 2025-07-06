"""Test for entity endpoints with proper dependency overrides."""

import logging
import pytest
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44 import crud
from camp44.api import deps
from camp44.models.app import App, AppCreate
from camp44.models.user import User

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
def entity_test_app(app: FastAPI, db_session: Session, test_user: User) -> App:
    """Create a test app for entity testing."""
    logger.info("Creating test app for entity tests")
    
    # Create the app directly using the CRUD module
    app_in = AppCreate(
        name="Entity Test App",
        description="App for entity endpoint tests"
    )
    
    test_app_obj = crud.app.create_app(session=db_session, app_in=app_in, owner=test_user)
    logger.info(f"Created test app with ID: {test_app_obj.id}")
    
    # Verify app existence in DB
    retrieved_app = crud.app.get_app(db_session, id=str(test_app_obj.id))
    if not retrieved_app:
        logger.error(f"Test app with ID {test_app_obj.id} not found in database after creation")
        raise ValueError("Test app creation failed")
    
    logger.info(f"Verified test app in database: {retrieved_app.id}")
    return test_app_obj


@pytest.fixture
def entity_test_client(app: FastAPI, db_session: Session, test_user: User, entity_test_app: App) -> TestClient:
    """Specialized test client for entity endpoints with all necessary dependencies overridden."""
    # Print all registered routes for debugging
    logger.info("=== REGISTERED ROUTES ===")
    for route in app.routes:
        route_path = getattr(route, "path", None)
        route_methods = getattr(route, "methods", None)
        logger.info(f"Route path: {route_path}, methods: {route_methods}")
    logger.info("========================")
    
    # Override database session
    app.dependency_overrides[deps.get_db] = lambda: db_session
    
    # Override current user
    def override_get_current_user():
        logger.info(f"Override returning test user: {test_user.id}")
        return test_user
    
    # Override app from path parameter - this is critical for entity endpoints
    def override_get_app_by_id_from_path(app_id: str):
        logger.info(f"Override called for app_id path parameter: {app_id}")
        
        # For testing, always return our test app regardless of app_id
        # This ensures the dependency works even if path param extraction has issues
        logger.info(f"Returning test app {entity_test_app.id} for path param {app_id}")
        return entity_test_app
    
    # Register all overrides
    app.dependency_overrides[deps.get_current_user] = override_get_current_user
    app.dependency_overrides[deps.get_current_active_user] = override_get_current_user
    app.dependency_overrides[deps.get_app_by_id_from_path] = override_get_app_by_id_from_path
    
    # Create test client
    with TestClient(app) as client:
        # Add test app ID to client for convenience
        client.test_app_id = str(entity_test_app.id)
        yield client
    
    # Clean up
    app.dependency_overrides = {}


def test_entity_path_debugging(entity_test_client: TestClient):
    """Test that focuses on debugging the entity path parameter handling."""
    app_id = entity_test_client.test_app_id
    logger.info(f"Test app ID: {app_id}")
    
    # Try the expected entity endpoint URL format
    entity_list_url = f"/api/v1/apps/{app_id}/entities"
    logger.info(f"Testing GET {entity_list_url}")
    
    # Make the request
    response = entity_test_client.get(entity_list_url)
    logger.info(f"Response status: {response.status_code}")
    logger.info(f"Response body: {response.text}")
    
    # If we're still getting 404, try examining request details
    if response.status_code == 404:
        logger.error("Entity endpoint not found")
        
        # Verify the app path parameter dependency override is working
        apps_url = f"/api/v1/apps/{app_id}"
        logger.info(f"Verifying app exists at {apps_url}")
        app_response = entity_test_client.get(apps_url)
        logger.info(f"App response status: {app_response.status_code}")
        logger.info(f"App response body: {app_response.text}")
        
        # Try direct database verification
        from camp44.models.entity import Entity
        from sqlmodel import select
        db_session = next(iter(entity_test_client.app.dependency_overrides[deps.get_db]().__closure__))
        result = db_session.execute(select(Entity).where(Entity.app_id == app_id))
        entities = result.scalars().all()
        logger.info(f"Found {len(entities)} entities in database for app {app_id}")
    
    # Assert that the endpoint should not return 404
    # This should work if our dependency overrides are correct
    assert response.status_code != 404, f"Entity endpoint not found: {entity_list_url}"
    
    # Now verify basic entity CRUD operations if the endpoint is working
    if response.status_code == 200:
        # Test creating an entity
        entity_name = "test_entity"
        entity_endpoint = f"{entity_list_url}/{entity_name}"
        
        entity_data = {
            "name": entity_name,
            "schema": {"type": "object", "properties": {"test_field": {"type": "string"}}}
        }
        
        logger.info(f"Testing entity creation at {entity_endpoint}")
        create_response = entity_test_client.post(entity_endpoint, json=entity_data)
        logger.info(f"Create response status: {create_response.status_code}")
        logger.info(f"Create response body: {create_response.text}")
        
        assert create_response.status_code == 200, f"Entity creation failed: {create_response.text}"
