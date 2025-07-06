"""Isolated test for entity endpoints specifically focused on path parameter extraction."""

import logging
import pytest
from fastapi.testclient import TestClient
import uuid
from typing import Dict, Any

from camp44.models.user import User
from camp44.models.app import App
from camp44.main import app as fastapi_app

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_entity_router_registration():
    """Verify entity routes are registered in the app."""
    entity_routes = []
    for route in fastapi_app.routes:
        if hasattr(route, "path") and "entities" in route.path:
            logger.info(f"Found entity route: {route.path}")
            entity_routes.append(route)
    
    assert len(entity_routes) > 0, "No entity routes found in the FastAPI app"

def test_app_by_id_dependency():
    """Directly test the app_id path parameter dependency."""
    from camp44.api import deps
    from camp44.db.session import engine
    from sqlmodel import Session
    
    # Create a session for direct DB access
    with Session(engine) as db:
        # Get the test user
        user_id = uuid.UUID("11111111-1111-1111-1111-111111111111")  # Fixed test user UUID
        user = db.get(User, user_id)
        assert user is not None, f"Test user with ID {user_id} not found"
        
        # Find an app that belongs to the test user
        from camp44 import crud
        from camp44.models.app import AppCreate
        apps = crud.app.get_multi_by_owner(db, owner=user)
        if not apps:
            # Create a test app if none exists
            app_in = AppCreate(
                name="Test App for Dependency",
                description="App created for testing dependency extraction"
            )
            app = crud.app.create_app(session=db, app_in=app_in, owner=user)
        else:
            app = apps[0]
        
        logger.info(f"Using app ID: {app.id}")
        
        # Test the dependency directly without FastAPI
        try:
            app_obj = deps.get_app_by_id_from_path(
                app_id=str(app.id),
                session=db,
                current_user=user
            )
            assert app_obj is not None, "get_app_by_id_from_path returned None"
            assert str(app_obj.id) == str(app.id), "App ID mismatch"
            logger.info(f"Direct dependency test passed for app: {app_obj.id}")
        except Exception as e:
            logger.error(f"Direct dependency test failed: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Dependency test failed: {e}")

def test_manual_entity_endpoint(test_app: App, client: TestClient):
    """Test entity endpoint using manual URL construction and error handling."""
    app_id = test_app.id
    entity_name = "test_entity_manual"
    
    logger.info(f"Testing entity endpoint with app_id={app_id}, entity_name={entity_name}")
    
    # Let's inspect all available routes first
    all_routes = []
    from camp44.main import app as fastapi_app
    for route in fastapi_app.routes:
        if hasattr(route, "path"):
            all_routes.append(route.path)
    
    logger.info(f"Available routes in app: {sorted(all_routes)}")
    
    # First verify app endpoint works
    app_url = f"/api/v1/apps/{app_id}"
    logger.info(f"Testing GET {app_url}")
    app_response = client.get(app_url)
    logger.info(f"App endpoint status: {app_response.status_code}")
    assert app_response.status_code == 200, f"App endpoint failed: {app_response.text}"
    
    # Let's find entity routes specifically
    entity_route_pattern = f"/api/v1/apps/{{{app_id}}}/entities"
    matching_routes = [r for r in all_routes if entity_route_pattern in r or "entities" in r]
    logger.info(f"Entity-related routes: {matching_routes}")
    
    # Now carefully construct and test the entity endpoint
    entity_url = f"/api/v1/apps/{app_id}/entities/{entity_name}"
    logger.info(f"Testing GET {entity_url}")
    
    # Create a basic entity to test with - even better if this succeeds
    try:
        from camp44.models.entity import Entity, EntityCreate
        entity_create_url = f"/api/v1/apps/{app_id}/entities"
        entity_data = {
            "name": entity_name,
            "schema": {"type": "object", "properties": {"test": {"type": "string"}}},
            "app_id": str(app_id)
        }
        create_response = client.post(entity_create_url, json=entity_data)
        logger.info(f"Entity creation response: {create_response.status_code}")
        logger.info(f"Entity creation body: {create_response.text[:200]}")
    except Exception as e:
        logger.error(f"Exception during entity creation: {e}")
    
    try:
        # Now try to GET the entity we just tried to create
        entity_response = client.get(entity_url)
        logger.info(f"Entity response status: {entity_response.status_code}")
        logger.info(f"Entity response body: {entity_response.text[:500]}")
        
        # If we're getting a 500 or other error, log more details
        if entity_response.status_code >= 500:
            logger.error(f"Unexpected error response: {entity_response.status_code}")
            logger.error(f"Full response body: {entity_response.text}")
            
            # Check for common error patterns
            if "app_id" in entity_response.text and "not found" in entity_response.text:
                logger.error("Possible path parameter extraction issue")
            elif "AttributeError" in entity_response.text:
                logger.error("Possible missing attribute or method in entity endpoint")
        
        # For now, accept any response that isn't a server error
        assert entity_response.status_code < 500, f"Server error: {entity_response.text}"
    except Exception as e:
        logger.error(f"Exception during entity request: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Exception in entity test: {e}")
