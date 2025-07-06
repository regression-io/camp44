import logging
import uuid
import json
import traceback

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44.models import User, App
from camp44 import crud
from camp44.models.entity import EntityCreate

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_entity_direct_access(client: TestClient, test_user: User, db_session: Session) -> None:
    """
    Test direct access to entity endpoints with detailed diagnostics.
    This test creates a test app, then tries to directly access entity endpoints
    with careful error handling and diagnostics.
    """
    try:
        # STEP 1: Create a test app using direct CRUD operations
        logger.info(f"Creating test app for user {test_user.id}")
        app_name = f"test-app-{uuid.uuid4()}"
        app_create = {
            "name": app_name,
            "description": "Test app for entity endpoint testing"
        }
        
        app = crud.app.create_app(
            session=db_session,
            app_in=app_create,
            owner=test_user
        )
        logger.info(f"Created test app: {app.id} - {app.name}")
        
        # Ensure the app is properly created and available
        assert app.id is not None
        assert app.owner_id == test_user.id
        
        # STEP 2: Log all available routes (sanity check)
        response = client.get("/openapi.json")
        assert response.status_code == 200
        
        paths = response.json().get("paths", {})
        logger.info("Available endpoints in OpenAPI schema:")
        for path in paths:
            logger.info(f"  Path: {path}")
            if "/entities/" in path:
                logger.info(f"    ** ENTITY PATH: {path}")
                logger.info(f"    Methods: {list(paths[path].keys())}")
        
        # STEP 3: First test GET /api/v1/apps/ to confirm TestClient works
        logger.info("Testing GET /api/v1/apps/ as sanity check")
        apps_response = client.get("/api/v1/apps/")
        logger.info(f"Apps endpoint status: {apps_response.status_code}")
        logger.info(f"Apps response (truncated): {apps_response.text[:200]}")
        assert apps_response.status_code == 200
        
        # STEP 4: Test entity creation endpoint
        entity_name = "test_entity"
        entity_endpoint = f"/api/v1/apps/{app.id}/entities/{entity_name}"
        
        # Create entity data
        entity_data = {
            "name": entity_name,
            "data": {"field1": "value1", "field2": 42}
        }
        
        logger.info(f"Making POST request to create entity: {entity_endpoint}")
        try:
            # Test with explicit content type
            headers = {"Content-Type": "application/json"}
            create_response = client.post(
                entity_endpoint, 
                data=json.dumps(entity_data),
                headers=headers
            )
            
            logger.info(f"Entity creation response status: {create_response.status_code}")
            logger.info(f"Entity creation response body: {create_response.text[:500]}")
            
            # If creation failed, try querying entities to check if endpoint exists
            if create_response.status_code != 201:
                logger.info(f"Entity creation failed, trying GET {entity_endpoint}")
                list_response = client.get(entity_endpoint)
                logger.info(f"Entity list response status: {list_response.status_code}")
                logger.info(f"Entity list response body: {list_response.text[:500]}")
                
            # Try another path format to see if that works
            alt_endpoint = f"/api/v1/apps/{app.id}/entities"
            logger.info(f"Trying alternate endpoint: GET {alt_endpoint}")
            alt_response = client.get(alt_endpoint)
            logger.info(f"Alternate endpoint response status: {alt_response.status_code}")
            logger.info(f"Alternate endpoint response body: {alt_response.text[:500]}")
            
        except Exception as e:
            logger.error(f"Exception during entity request: {e}")
            logger.error("Full error traceback:")
            traceback.print_exc()
            raise
            
    except Exception as e:
        logger.error(f"TOP LEVEL EXCEPTION: {e}")
        logger.error("Full error traceback:")
        traceback.print_exc()
        raise
