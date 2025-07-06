import logging
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def normalize_path(path: str) -> str:
    """Normalize path for comparison by replacing path params with placeholders"""
    return re.sub(r'{[^}]+}', '{param}', path)

def test_entity_router_registry(app: FastAPI) -> None:
    """Test if entity router is properly registered in the FastAPI app."""
    # Extract all paths from app routes
    all_paths = []
    for route in app.routes:
        if hasattr(route, "path"):
            all_paths.append(route.path)
            methods = list(route.methods) if hasattr(route, "methods") else []
            logger.info(f"Route: {route.path}, Methods: {methods}")
    
    # Log all found paths
    logger.info("All registered paths:")
    for idx, path in enumerate(all_paths):
        logger.info(f"{idx}: {path}")
    
    # Check for entity-related paths specifically
    entity_paths = []
    apps_paths = []
    for path in all_paths:
        if '/entities/' in path or '/entities' == path[-9:]:
            entity_paths.append(path)
        if '/apps/' in path:
            apps_paths.append(path)
    
    logger.info("App-related paths:")
    for path in apps_paths:
        logger.info(f"  {path}")
        
    logger.info("Entity-related paths:")
    for path in entity_paths:
        logger.info(f"  {path}")
    
    # Ensure entity endpoint paths are present
    expected_entity_path_pattern = "/api/v1/apps/{app_id}/entities/{entity_name}"
    
    # Deep inspection of all paths for similar structure
    similar_paths = []
    for path in all_paths:
        path_normalized = normalize_path(path)
        expected_normalized = normalize_path(expected_entity_path_pattern)
        if path_normalized.count('/') == expected_normalized.count('/'):
            similar_paths.append((path, path_normalized))
    
    logger.info("Paths with similar structure to entity paths:")
    for orig_path, norm_path in similar_paths:
        logger.info(f"  {orig_path} -> {norm_path}")
    
    # Log routes where a path parameter comes before a specific path segment
    param_before_segment_paths = []
    for path in all_paths:
        if re.search(r'{[^}]+}/[^{/]+', path):
            param_before_segment_paths.append(path)
    
    logger.info("Path parameter followed by path segment:")
    for path in param_before_segment_paths:
        logger.info(f"  {path}")
    
    # Now check the specific entity paths we expect
    assert "/api/v1/apps/{app_id}/entities/{entity_name}" in all_paths, "Entity endpoint path not found"
    
    # Explicitly log openapi.json access to debug route registration
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200, "Failed to get OpenAPI schema"
    
    api_schema = response.json()
    logger.info("Paths in OpenAPI schema:")
    for path in api_schema.get("paths", {}):
        logger.info(f"  {path}")
