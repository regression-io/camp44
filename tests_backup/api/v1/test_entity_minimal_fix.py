"""Minimal test focusing on entity endpoint URL structure and path parameter extraction."""

import logging
import pytest
import uuid
from fastapi.testclient import TestClient

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_entity_endpoint_minimal(client: TestClient):
    """Test just the entity endpoints with minimal setup and focused diagnostics."""
    # First create a test app to use as our target
    app_data = {"name": "Entity Test App"}
    app_response = client.post("/api/v1/apps/", json=app_data)
    
    assert app_response.status_code == 200, f"Failed to create app: {app_response.text}"
    app_id = app_response.json()["id"]
    logger.info(f"Created test app with ID: {app_id}")
    
    # Now log the exact URL structure we're going to use
    entity_list_url = f"/api/v1/apps/{app_id}/entities"
    logger.info(f"Entity list URL: {entity_list_url}")
    
    # Direct inspection of the FastAPI app routes
    from camp44.main import app as fastapi_app
    
    # Find all routes matching our entity path pattern
    entity_routes = []
    for route in fastapi_app.routes:
        if hasattr(route, "path") and "entities" in route.path:
            entity_routes.append(route)
    
    logger.info(f"Found {len(entity_routes)} entity-related routes")
    for route in entity_routes:
        logger.info(f"Route path: {route.path}")
        logger.info(f"Route methods: {getattr(route, 'methods', [])}")
        if hasattr(route, "endpoint") and hasattr(route.endpoint, "__name__"):
            logger.info(f"Route endpoint: {route.endpoint.__name__}")
    
    # Test the entity list endpoint (GET)
    try:
        entity_list_response = client.get(entity_list_url)
        logger.info(f"Entity list response status: {entity_list_response.status_code}")
        logger.info(f"Entity list response body: {entity_list_response.text}")
        # Note: no assertion here - we're just diagnosing
        
        # Now test with a specific entity name
        entity_name = "test_entity"
        entity_name_url = f"{entity_list_url}/{entity_name}"
        logger.info(f"Entity name URL: {entity_name_url}")
        
        entity_name_response = client.get(entity_name_url)
        logger.info(f"Entity name response status: {entity_name_response.status_code}")
        logger.info(f"Entity name response body: {entity_name_response.text}")
        
        # If the above worked, try creating an entity
        entity_data = {
            "name": entity_name,
            "schema": {"type": "object", "properties": {}}
        }
        
        create_response = client.post(entity_name_url, json=entity_data)
        logger.info(f"Create entity response status: {create_response.status_code}")
        logger.info(f"Create entity response body: {create_response.text}")
        
        if create_response.status_code == 200:
            # If entity was created, get its ID
            entity_id = create_response.json().get("id")
            if entity_id:
                # Try to retrieve the specific entity
                entity_url = f"{entity_name_url}/{entity_id}"
                logger.info(f"Entity URL: {entity_url}")
                
                get_entity_response = client.get(entity_url)
                logger.info(f"Get entity response status: {get_entity_response.status_code}")
                logger.info(f"Get entity response body: {get_entity_response.text}")
    except Exception as e:
        logger.error(f"Exception during entity test: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Clean up no matter what happened
    try:
        delete_app_response = client.delete(f"/api/v1/apps/{app_id}")
        logger.info(f"App cleanup status: {delete_app_response.status_code}")
    except Exception as e:
        logger.error(f"Error cleaning up app: {e}")
