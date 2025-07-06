"""Diagnostic test for entity endpoints focusing on path parameter handling."""

import logging
import pytest
import uuid
from fastapi.testclient import TestClient

from camp44.models.user import User
from camp44.models.app import App

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_app_endpoint(client: TestClient) -> None:
    """Test that the basic app endpoint works as a control case."""
    # Create a test app
    app_data = {"name": "Diagnostic Test App"}
    response = client.post("/api/v1/apps/", json=app_data)
    
    logger.info(f"App creation status: {response.status_code}")
    
    assert response.status_code == 200, f"Failed to create app: {response.text}"
    app_id = response.json()["id"]
    
    # Test that we can get the app
    app_response = client.get(f"/api/v1/apps/{app_id}")
    logger.info(f"App get status: {app_response.status_code}")
    assert app_response.status_code == 200, "Failed to get app"
    
    # Clean up
    client.delete(f"/api/v1/apps/{app_id}")


def test_entity_endpoint_manual_app(client: TestClient) -> None:
    """Test entity endpoint with manual app creation and detailed diagnostics."""
    # First create an app to use
    app_data = {"name": "Entity Test App"}
    response = client.post("/api/v1/apps/", json=app_data)
    assert response.status_code == 200, f"Failed to create app: {response.text}"
    app_id = response.json()["id"]
    logger.info(f"Created test app with ID: {app_id}")
    
    # Manually override path parameters
    from camp44.main import app as fastapi_app
    from fastapi import Request, Depends
    from sqlmodel import Session
    from camp44.api import deps
    from camp44.models.app import App
    
    # Check which dependency is being used in the route
    entity_routes = [r for r in fastapi_app.routes if hasattr(r, "path") and "entities" in r.path]
    logger.info("Entity routes:")
    for route in entity_routes:
        logger.info(f"  Path: {route.path}")
        if hasattr(route, "endpoint") and hasattr(route.endpoint, "__name__"):
            logger.info(f"  Endpoint: {route.endpoint.__name__}")
    
    # Test entity endpoint with direct access
    entity_name = "diagnostic_entity"
    entity_url = f"/api/v1/apps/{app_id}/entities"
    logger.info(f"Testing GET {entity_url}")

    # First try to create an entity
    entity_data = {
        "name": entity_name,
        "schema": {"type": "object", "properties": {}}
    }
    
    # Test GET on the entity list endpoint first (simplest case)
    try:
        logger.info(f"GET request to entity list URL: {entity_url}")
        entity_list_response = client.get(entity_url)
        logger.info(f"Entity list response status: {entity_list_response.status_code}")
        logger.info(f"Entity list response body: {entity_list_response.text}")
        
        if entity_list_response.status_code == 200:
            logger.info("SUCCESS! Entity list endpoint passed.")
        else:
            logger.info("Entity list endpoint failed with non-200 response")
    except Exception as e:
        logger.error(f"Exception on entity list request: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Now try POST to create entity
    try:
        create_url = f"{entity_url}/{entity_name}"
        logger.info(f"POST request to create entity URL: {create_url}")
        logger.info(f"Entity data: {entity_data}")
        
        entity_create_response = client.post(
            create_url,
            json=entity_data
        )
        logger.info(f"Entity create response status: {entity_create_response.status_code}")
        logger.info(f"Entity create response body: {entity_create_response.text}")
        
        if entity_create_response.status_code == 200:
            logger.info("SUCCESS! Entity creation passed")
            
            # Now try to GET the entity
            entity_id = entity_create_response.json()["id"]
            get_entity_url = f"{entity_url}/{entity_name}/{entity_id}"
            logger.info(f"GET request to entity URL: {get_entity_url}")
            
            get_response = client.get(get_entity_url)
            logger.info(f"Get entity response status: {get_response.status_code}")
            logger.info(f"Get entity response body: {get_response.text}")
            
            if get_response.status_code == 200:
                logger.info("SUCCESS! Entity get passed")
            else:
                logger.info("Entity get failed with non-200 response")
        else:
            logger.info("Entity creation failed with non-200 response")
    except Exception as e:
        logger.error(f"Exception on entity creation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Clean up
    client.delete(f"/api/v1/apps/{app_id}")
