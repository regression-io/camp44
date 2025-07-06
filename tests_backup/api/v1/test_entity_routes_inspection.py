"""Test script to inspect route registration for entity endpoints."""

import pytest
from fastapi.testclient import TestClient
import logging

logger = logging.getLogger(__name__)

def test_inspect_routes(client: TestClient):
    """Directly inspect all routes registered in the FastAPI app."""
    from camp44.main import app
    
    # Get all routes
    routes = app.routes
    
    # First inspect general route structure
    logger.info("====== All Routes ======")
    all_paths = []
    for route in routes:
        if hasattr(route, "path"):
            path = route.path
            methods = getattr(route, "methods", [])
            logger.info(f"Path: {path}, Methods: {methods}")
            all_paths.append(path)
    
    # Now focus on entity-related routes
    entity_routes = [r for r in routes if hasattr(r, "path") and "entities" in r.path]
    
    logger.info("\n====== Entity Routes ======")
    for route in entity_routes:
        path = route.path
        methods = getattr(route, "methods", [])
        endpoint_fn = getattr(route, "endpoint", None)
        endpoint_name = endpoint_fn.__name__ if endpoint_fn else "Unknown"
        
        logger.info(f"Path: {path}")
        logger.info(f"Methods: {methods}")
        logger.info(f"Endpoint function: {endpoint_name}")
        
        # Check if the route has path parameters
        path_params = []
        for part in path.split("/"):
            if part.startswith("{") and part.endswith("}"):
                path_params.append(part[1:-1])  # Remove { and }
        
        logger.info(f"Path parameters: {path_params}")
        
        # Inspect endpoint dependencies
        if endpoint_fn:
            deps = getattr(endpoint_fn, "dependencies", [])
            logger.info(f"Dependencies: {deps}")
            
            # Check function signature
            import inspect
            sig = inspect.signature(endpoint_fn)
            logger.info(f"Function signature: {sig}")
        
        logger.info("---")
    
    # Try to make a request to the entity list endpoint
    test_app_response = client.post("/api/v1/apps/", json={"name": "Route Test App"})
    assert test_app_response.status_code == 200, f"Failed to create app: {test_app_response.text}"
    
    app_id = test_app_response.json()["id"]
    logger.info(f"\nCreated test app with ID: {app_id}")
    
    # Now try the entity list endpoint
    entity_list_url = f"/api/v1/apps/{app_id}/entities"
    logger.info(f"Testing entity list endpoint: GET {entity_list_url}")
    
    try:
        response = client.get(entity_list_url)
        logger.info(f"Response status: {response.status_code}")
        logger.info(f"Response body: {response.text}")
        
        # Don't assert here, just collect info
    except Exception as e:
        logger.error(f"Exception when accessing {entity_list_url}: {e}")
        import traceback
        logger.error(traceback.format_exc())
    
    # Clean up
    client.delete(f"/api/v1/apps/{app_id}")
