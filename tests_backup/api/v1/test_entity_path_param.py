"""Test specifically focused on the app_id path parameter handling for entity endpoints."""
import logging
import sys
import traceback
import inspect
import uuid
from typing import Dict, Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from camp44.models import User, App
from camp44.main import app as fastapi_app

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_entity_path_param_handling(client: TestClient, test_user: User, test_app: App) -> None:
    """Test that focuses specifically on handling the app_id path parameter."""
    try:
        # Log test app details for debugging
        logger.debug(f"Test app ID: {test_app.id}")
        logger.debug(f"Test app owner ID: {test_app.owner_id}")
        logger.debug(f"Test user ID: {test_user.id}")
        
        # Verify that app was created with correct ownership
        assert test_app.owner_id == test_user.id, "Test app not owned by test user"
        
        # Enable detailed logging for this test
        logger.getLogger('httpx').setLevel(logging.DEBUG)
        logger.getLogger('fastapi').setLevel(logging.DEBUG)
        
        # Print the route that we're trying to access
        entity_name = "test_entity"
        path = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        logger.debug(f"Attempting to access path: {path}")
        
        # Log all routes for reference
        logger.debug("All registered routes with 'entities':")
        for route in fastapi_app.routes:
            if hasattr(route, "path") and "entities" in route.path:
                logger.debug(f"Route: {route.path}")
                
        # Try with direct query parameters instead of path parameters
        try:
            logger.debug(f"Testing with query param: /api/v1/apps/{test_app.id}/entities/{entity_name}")
            response = client.get(path)
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response body: {response.text[:200]}")
        except Exception as e:
            logger.error(f"Error accessing entities with path: {e}")
            traceback.print_exc()

        # Try a different approach for path parameters
        path_explicit = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        try:
            logger.debug(f"Testing with explicit path param: {path_explicit}")
            # Try with different HTTP methods
            for method in ["GET", "POST"]:
                try:
                    if method == "GET":
                        logger.debug(f"Testing GET {path_explicit}")
                        response = client.get(path_explicit)
                    elif method == "POST":
                        logger.debug(f"Testing POST {path_explicit}")
                        payload = {"name": entity_name, "data": {"test": "value"}}
                        response = client.post(path_explicit, json=payload)
                    
                    logger.debug(f"{method} Response status: {response.status_code}")
                    logger.debug(f"{method} Response body: {response.text[:200]}")
                except Exception as e:
                    logger.error(f"Error with {method} {path_explicit}: {e}")
                    traceback.print_exc()
        except Exception as e:
            logger.error(f"Error with explicit path: {e}")
            traceback.print_exc()
            
        # Test if the app_id in the path is correctly accessed in the dependency
        # Create a simple app endpoint test to verify path parameter extraction works
        app_path = f"/api/v1/apps/{test_app.id}"
        try:
            logger.debug(f"Testing app endpoint as reference: {app_path}")
            response = client.get(app_path)
            logger.debug(f"App endpoint response status: {response.status_code}")
            logger.debug(f"App endpoint response body: {response.text[:200]}")
        except Exception as e:
            logger.error(f"Error accessing app endpoint: {e}")
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"Top-level exception: {e}")
        traceback.print_exc()
        raise
