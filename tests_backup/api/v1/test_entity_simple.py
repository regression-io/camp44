"""Simple, isolated test for entity endpoints with path parameter extraction."""

import logging
import pytest
import uuid
from fastapi.testclient import TestClient

from camp44.models.user import User
from camp44.models.app import App

# Set up logging with a specific format to make path parameter info clear
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


def test_entity_simple_get(client: TestClient, test_app: App) -> None:
    """Test basic GET entity endpoint with focus on path parameter extraction."""
    # Create a simple test
    entity_name = "test_entity_simple"
    
    # First verify we can access the app (this should work)
    app_path = f"/api/v1/apps/{test_app.id}"
    logger.info(f"Testing GET {app_path}")
    response = client.get(app_path)
    logger.info(f"App response status: {response.status_code}")
    assert response.status_code == 200, f"App endpoint failed: {response.text}"
    
    # Now try to access the entity endpoint - we expect a 404 since the entity doesn't exist
    # But we should at least get to the endpoint handler without parameter extraction errors
    entity_path = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
    logger.info(f"Testing GET {entity_path}")
    
    # Add verbose logging to the client request
    response = None
    try:
        response = client.get(entity_path)
        logger.info(f"Entity GET response status: {response.status_code}")
        logger.info(f"Response body: {response.text}")
        
        # We expect a 404 (entity doesn't exist yet), but not a 500 or other error
        assert response.status_code == 404, f"Expected 404 for non-existent entity, got {response.status_code}"
    except Exception as e:
        logger.error(f"Exception during entity GET: {e}")
        import traceback
        traceback.print_exc()
        pytest.fail(f"Exception in entity request: {e}")
