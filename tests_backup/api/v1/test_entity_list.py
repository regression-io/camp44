"""Super minimal test for entity endpoint that just lists all entities."""

import logging
import pytest
import uuid
from fastapi.testclient import TestClient

from camp44.models.user import User
from camp44.models.app import App

# Set up logging with a specific format to make path parameter info clear
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_entity_list(client: TestClient, test_app: App) -> None:
    """Test just listing all entities for an app."""
    app_id = test_app.id
    
    # First verify we can access the app (this should work)
    app_path = f"/api/v1/apps/{app_id}"
    logger.info(f"Testing GET {app_path}")
    response = client.get(app_path)
    logger.info(f"App response status: {response.status_code}")
    assert response.status_code == 200, f"App endpoint failed: {response.text}"
    
    # Now try to list all entities for this app - this should return an empty list
    # But we should at least get to the endpoint handler without parameter extraction errors
    entities_path = f"/api/v1/apps/{app_id}/entities"
    logger.info(f"Testing GET {entities_path}")
    
    try:
        response = client.get(entities_path)
        logger.info(f"Entity list response status: {response.status_code}")
        logger.info(f"Response body: {response.text}")
        
        # We expect a 200 with an empty list
        assert response.status_code == 200, f"Expected 200 for entity list endpoint, got {response.status_code}: {response.text}"
        
        # If we got this far, try to create an entity
        entity_data = {
            "name": "test_entity",
            "schema": {"type": "object", "properties": {"test": {"type": "string"}}},
            "app_id": str(app_id)
        }
        logger.info(f"Creating entity with data: {entity_data}")
        create_response = client.post(entities_path + "/test_entity", json=entity_data)
        logger.info(f"Entity creation response: {create_response.status_code}")
        logger.info(f"Creation response body: {create_response.text}")
        
        # Check if creation was successful
        if create_response.status_code == 200:
            # Try to get the created entity
            get_response = client.get(entities_path + "/test_entity")
            logger.info(f"Get entity response: {get_response.status_code}")
            logger.info(f"Get response body: {get_response.text}")
        
    except Exception as e:
        logger.error(f"Exception during entity list request: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Exception in entity list request: {e}")
