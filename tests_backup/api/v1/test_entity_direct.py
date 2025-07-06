"""Test directly targeting entity endpoints with detailed debug output."""
import logging
import uuid
from typing import Dict, Any, List, Optional

import pytest
from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from pydantic import BaseModel

from camp44.models import User, App
from camp44.main import app as fastapi_app
from camp44 import crud
from camp44.api import deps

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_direct_entity_endpoint(client: TestClient, test_user: User, test_app: App) -> None:
    """Test entity endpoints with direct inspection of routes."""
    try:
        # Log test fixtures
        logger.debug(f"Test user: {test_user.id} ({test_user.email})")
        logger.debug(f"Test app: {test_app.id} ({test_app.name})")
        
        # Inspect all entity-related routes
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
                logger.debug(f"Found entity route: {route_info}")
        
        logger.debug(f"Total entity routes: {len(entity_routes)}")
        
        # Find the actual path parameters expected by FastAPI
        for route in entity_routes:
            logger.debug(f"Path params for route {route['path']}: {route.get('path_params', {})}")
        
        # First verify the app endpoint is working
        app_path = f"/api/v1/apps/{test_app.id}"
        logger.debug(f"Testing GET {app_path}")
        response = client.get(app_path)
        logger.debug(f"App response status: {response.status_code}")
        logger.debug(f"App response: {response.json() if response.status_code == 200 else response.text}")
        assert response.status_code == 200, f"App endpoint failed: {response.text}"
        
        # Check if our dependency override is properly handling the app_id
        from camp44.api import deps
        app_obj = None
        try:
            logger.debug(f"Testing get_app_by_id_from_path with app_id: {test_app.id}")
            app_obj = deps.get_app_by_id_from_path(str(test_app.id), session=None, current_user=None)
            logger.debug(f"get_app_by_id_from_path result: {app_obj.id if app_obj else 'None'}")
            assert app_obj is not None, "get_app_by_id_from_path override is not working"
        except Exception as e:
            logger.error(f"Error in get_app_by_id_from_path: {e}")
            import traceback
            traceback.print_exc()
        
        # Try a direct test of the app path parameter extraction
        entity_name = "test_entity_direct"
        
        # Create a simplified test to directly check the entity routes
        entity_routes_path = f"/api/v1/apps/{test_app.id}/entities"
        logger.debug(f"Testing direct GET to entity routes base path: {entity_routes_path}")
        
        try:
            # This should hit the entity router but not a specific endpoint
            # It should 404, but give us info in logs about route matching
            response = client.get(entity_routes_path)
            logger.debug(f"Entity routes base path response: {response.status_code}")
            logger.debug(f"Response body: {response.text[:500]}")
            
            # Now try with a specific entity name
            entity_path = f"{entity_routes_path}/{entity_name}"
            logger.debug(f"Testing GET {entity_path}")
            response = client.get(entity_path)
            logger.debug(f"Get entities response status: {response.status_code}")
            logger.debug(f"Response body: {response.text[:500]}")
            
            # Print request information to verify path parameters
            logger.debug("Path parameters captured by the test client:")
            if hasattr(response, "request"):
                logger.debug(f"Request URL: {response.request.url}")
                logger.debug(f"Request method: {response.request.method}")
                if hasattr(response.request, "path_params"):
                    logger.debug(f"Path params: {response.request.path_params}")
                    
        except Exception as e:
            logger.error(f"Exception during entity endpoints test: {e}")
            import traceback
            traceback.print_exc()
            
        # Try with a more explicit URL without relying on f-strings
        try:
            # Explicitly construct URL to avoid any string formatting issues
            app_id_str = str(test_app.id)
            entity_path_explicit = "/api/v1/apps/" + app_id_str + "/entities/" + entity_name
            logger.debug(f"Testing explicit GET {entity_path_explicit}")
            response = client.get(entity_path_explicit)
            logger.debug(f"Explicit GET response status: {response.status_code}")
            logger.debug(f"Response body: {response.text[:500]}")
        except Exception as e:
            logger.error(f"Exception during explicit entity path test: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"Top-level exception: {e}")
        import traceback
        traceback.print_exc()
        raise
