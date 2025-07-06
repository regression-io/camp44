"""Test entity endpoints with focus on path parameter extraction."""

import logging
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
import uuid
from urllib.parse import quote

from camp44.models.user import User
from camp44.models.app import App
from camp44.api.v1.endpoints import entities
from camp44.main import app as fastapi_app

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_entity_router_registration():
    """Test that entity router paths are correctly registered."""
    # Find and log all entity-related routes
    entity_routes = []
    for route in fastapi_app.routes:
        if hasattr(route, "path") and "entities" in route.path:
            route_info = {
                "path": route.path,
                "methods": list(getattr(route, "methods", set())),
                "name": getattr(route, "name", None),
                "endpoint": getattr(route.endpoint, "__name__", str(route.endpoint)) if hasattr(route, "endpoint") else None,
                "path_params": getattr(route, "param_convertors", {}),
            }
            entity_routes.append(route_info)
            logger.info(f"Found entity route: {route_info}")
    
    # Verify that entity routes exist
    assert len(entity_routes) > 0, "No entity routes found in the FastAPI app"
    logger.info(f"Total entity routes found: {len(entity_routes)}")

def test_entity_path_parameters(client: TestClient, test_app: App):
    """Test that entity endpoint path parameters are correctly extracted."""
    # Log test fixtures
    logger.info(f"Test app ID: {test_app.id}")
    
    # Create a direct route to test path parameter extraction
    entity_name = "test_entity_path"
    app_id_str = str(test_app.id)
    
    # Test the GET entities endpoint
    url = f"/api/v1/apps/{app_id_str}/entities/{entity_name}"
    
    # Log request URL with guaranteed URL encoding
    encoded_url = "/api/v1/apps/" + quote(app_id_str) + "/entities/" + quote(entity_name)
    logger.info(f"Testing GET request to URL: {url}")
    logger.info(f"URL-encoded version: {encoded_url}")
    
    # Make request and capture any path parameter debug logs
    response = client.get(url)
    
    # Log response details
    logger.info(f"Response status code: {response.status_code}")
    
    # Even though we expect a 404 (entity doesn't exist yet), the path parameter extraction
    # should still work and we should see debug logs for the endpoint handler
    if response.status_code == 404:
        logger.info("Got 404 as expected (entity doesn't exist yet)")
    else:
        logger.info(f"Got unexpected status: {response.status_code}")
        logger.info(f"Response body: {response.text[:500]}")

def test_direct_app_dependency(client: TestClient, test_app: App):
    """Test the app_id path parameter extraction directly."""
    from camp44.api import deps
    
    # Get the test app ID
    app_id_str = str(test_app.id)
    logger.info(f"Testing get_app_by_id_from_path with app_id: {app_id_str}")
    
    # Try to get the app directly through the dependency
    try:
        # This should use our dependency override from conftest.py
        app_obj = deps.get_app_by_id_from_path(app_id_str)
        assert app_obj is not None, "App dependency returned None"
        assert str(app_obj.id) == app_id_str, "App ID mismatch"
        logger.info(f"Successfully retrieved app with ID {app_obj.id}")
    except Exception as e:
        logger.error(f"Error in get_app_by_id_from_path: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"App dependency failed: {e}")
