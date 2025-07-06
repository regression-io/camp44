"""Test to debug entity path parameter handling with detailed logging."""
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

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PathParamLoggerRoute(APIRoute):
    """Custom route class that logs path parameter extraction."""
    
    def get_route_handler(self):
        original_route_handler = super().get_route_handler()
        
        def custom_route_handler(request: Request):
            logger.debug(f"ROUTE DEBUG - Path: {request.url.path}")
            logger.debug(f"ROUTE DEBUG - Path params: {request.path_params}")
            try:
                response = original_route_handler(request)
                return response
            except Exception as exc:
                logger.error(f"ROUTE DEBUG - Exception in route handler: {exc}")
                raise
                
        return custom_route_handler

def test_debug_app_route(client: TestClient, test_user: User, test_app: App) -> None:
    """Test app route to compare with entity route."""
    logger.debug(f"Test app ID: {test_app.id}")
    
    # First test a known working route (app retrieval)
    app_path = f"/api/v1/apps/{test_app.id}"
    try:
        logger.debug(f"Testing GET {app_path}")
        response = client.get(app_path)
        logger.debug(f"App response status: {response.status_code}")
        logger.debug(f"App response: {response.json() if response.status_code == 200 else response.text}")
        
        # Now log all routes for reference
        all_routes = []
        entity_routes = []
        
        for route in fastapi_app.routes:
            if not hasattr(route, "path"):
                continue
                
            route_info = {
                "path": route.path,
                "methods": list(getattr(route, "methods", set())),
                "name": getattr(route, "name", None),
                "endpoint": getattr(route.endpoint, "__name__", str(route.endpoint)) if hasattr(route, "endpoint") else None,
                "path_params": [p for p in route.path_regex.pattern.split("/") if p.startswith("{") and p.endswith("}")],
            }
            all_routes.append(route_info)
            
            if "entities" in route.path:
                entity_routes.append(route_info)
                logger.debug(f"Entity route: {route_info}")
        
        logger.debug(f"Total routes: {len(all_routes)}")
        logger.debug(f"Entity routes: {len(entity_routes)}")
        
        # Try entity endpoint
        entity_name = "test_entity"
        entity_path = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        logger.debug(f"Testing GET {entity_path}")
        
        try:
            response = client.get(entity_path)
            logger.debug(f"Entity response status: {response.status_code}")
            logger.debug(f"Entity response: {response.json() if response.status_code == 200 else response.text}")
        except Exception as e:
            logger.error(f"Exception during entity request: {e}")
            import traceback
            traceback.print_exc()
            
    except Exception as e:
        logger.error(f"Top-level exception: {e}")
        import traceback
        traceback.print_exc()
        raise
        
    # Compare URL pattern matches
    for eroute in entity_routes:
        path_pattern = eroute["path"]
        # Replace path params with actual values for testing
        test_path = path_pattern.replace("{app_id}", str(test_app.id))
        if "{entity_name}" in test_path:
            test_path = test_path.replace("{entity_name}", "test_entity")
        # Test with this exact path
        try:
            logger.debug(f"Testing exact path match: {test_path}")
            response = client.get(test_path)
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response: {response.text[:200]}")
        except Exception as e:
            logger.error(f"Exception with {test_path}: {e}")
