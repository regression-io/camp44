import logging
import uuid
import json
from typing import Dict, Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44.models import User, App
from camp44 import crud
from camp44.api import deps

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_entity_focused(client: TestClient, test_user: User, db_session: Session) -> None:
    """
    Focused test for entity endpoints with explicit app creation and direct dependency usage.
    This test simulates what happens when FastAPI tries to extract the app_id from the path.
    """
    # STEP 1: Create a test app with a known ID for direct access
    test_app_id = str(uuid.uuid4())
    app_create = {
        "name": f"test-app-{test_app_id[:8]}",
        "description": "Test app for entity endpoint testing"
    }
    
    # Create the app directly with CRUD function
    app = crud.app.create_app(
        session=db_session,
        app_in=app_create, 
        owner=test_user
    )
    
    logger.info(f"Created test app: {app.id} (UUID: {type(app.id)}) - {app.name}")
    
    # STEP 2: Verify the app exists in the database via API
    response = client.get(f"/api/v1/apps/{app.id}")
    logger.info(f"GET app response: {response.status_code}")
    if response.status_code == 200:
        logger.info("App found via API")
    else:
        logger.error(f"Failed to get app via API: {response.text}")
    
    # STEP 3: Test entity endpoints with explicit debugging
    entity_name = "test_entity"
    entity_data = {
        "name": entity_name,
        "data": {"key1": "value1", "key2": 42}
    }
    
    # Test the dependency directly first
    try:
        # Try calling the dependency function directly to see if it works
        # This simulates what FastAPI would do when processing a request
        app_from_dep = deps.get_app_by_id_from_path(
            app_id=str(app.id),
            session=db_session,
            current_user=test_user
        )
        logger.info(f"Dependency direct call succeeded: app_id={app_from_dep.id}")
    except Exception as e:
        logger.error(f"Dependency direct call failed: {e}")
        
    # Now test the entity endpoint with the correct URL
    url = f"/api/v1/apps/{app.id}/entities/{entity_name}"
    logger.info(f"Testing POST to {url}")
    
    headers = {"Content-Type": "application/json"}
    entity_response = client.post(
        url,
        data=json.dumps(entity_data),
        headers=headers
    )
    
    logger.info(f"Entity creation response: {entity_response.status_code}")
    logger.info(f"Entity response body: {entity_response.text[:200]}")
    
    # If that failed, try the GET endpoint which should return an empty list
    if entity_response.status_code >= 400:
        logger.info(f"Testing GET to {url}")
        list_response = client.get(url)
        logger.info(f"Entity list response: {list_response.status_code}")
        logger.info(f"Entity list response body: {list_response.text[:200]}")
