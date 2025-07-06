"""Test for detailed route registration inspection."""

import logging
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.routing import APIRoute

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_route_registration_inspection(app: FastAPI) -> None:
    """Inspect all registered routes to find entity/app endpoints."""
    print("\n=== INSPECTING ALL ROUTE REGISTRATIONS ===")
    
    # Store original routes
    all_routes = []
    for route in app.routes:
        if not hasattr(route, "path"):
            continue
            
        path = route.path
        methods = list(getattr(route, "methods", set()))
        name = getattr(route, "name", None)
        endpoint_name = getattr(route.endpoint, "__name__", str(route.endpoint)) if hasattr(route, "endpoint") else None
        
        route_info = {
            "path": path,
            "methods": methods, 
            "name": name,
            "endpoint": endpoint_name
        }
        all_routes.append(route_info)
    
    # Log all routes for clarity
    logger.info(f"Found {len(all_routes)} total routes")
    for route in all_routes:
        logger.info(f"  {route['methods']} {route['path']} -> {route['endpoint']}")
    
    # Check main.py router includes
    from camp44.main import app as main_app
    logger.info("Verifying entity router registration in main.py:")
    for route in main_app.routes:
        if not hasattr(route, "path"):
            continue
        path = getattr(route, "path", "<no path>")
        if "entities" in path:
            logger.info(f"  MAIN APP ENTITY ROUTE: {path}")
    
    # Check if the entity router is part of the app's namespace
    logger.info("Checking all namespaces in the app:")
    from camp44.api.v1.endpoints import entities
    logger.info(f"Entity router exists: {hasattr(entities, 'router')}")
    
    # Examine app router structures more deeply
    logger.info("Examining app routers:")
    routers = []
    
    # Function to recursively find all nested routers
    def collect_routers(router, prefix=""):
        if hasattr(router, "routes"):
            for route in router.routes:
                if hasattr(route, "app") and route.app is not None:
                    # This is a mounted app or sub-router
                    sub_prefix = prefix + route.path
                    logger.info(f"Found sub-router or mounted app at: {sub_prefix}")
                    routers.append((sub_prefix, route.app))
                    collect_routers(route.app, sub_prefix)
    
    # Examine the main app for nested routers
    collect_routers(app)
    
    # Check for specific entity endpoints
    logger.info("Looking for specific entity endpoints:")
    found_endpoints = {
        "list": False,
        "create": False,
        "update": False,
        "delete": False
    }
    
    for route in all_routes:
        path = route['path']
        # Check for entity endpoints patterns
        if "{app_id}" in path and "entities" in path:
            if "{entity_name}" in path:
                if "POST" in route['methods'] or "PUT" in route['methods']:
                    found_endpoints["create"] = True
                    logger.info(f"Found entity creation endpoint: {route['methods']} {path}")
                if "GET" in route['methods']:
                    if "{id}" in path:  # Pattern for single entity
                        logger.info(f"Found entity get endpoint: {route['methods']} {path}")
                    else:
                        found_endpoints["list"] = True
                        logger.info(f"Found entity list endpoint: {route['methods']} {path}")
                if "PATCH" in route['methods']:
                    found_endpoints["update"] = True
                    logger.info(f"Found entity update endpoint: {route['methods']} {path}")
                if "DELETE" in route['methods']:
                    found_endpoints["delete"] = True
                    logger.info(f"Found entity delete endpoint: {route['methods']} {path}")
    
    logger.info(f"Entity endpoints found: {found_endpoints}")
    
    # Compare with hardcoded list of expected endpoints to diagnose possible import issues
    logger.info("=== EXPECTED ROUTES CHECK ===")
    expected_entity_patterns = [
        "/api/v1/apps/{app_id}/entities/{entity_name}",
        "/api/v1/apps/{app_id}/entities/{entity_name}/{id}"
    ]
    
    expected_found = False
    for pattern in expected_entity_patterns:
        found = any(pattern == route['path'] for route in all_routes)
        logger.info(f"Expected route {pattern}: {'FOUND' if found else 'NOT FOUND'}")
        if found:
            expected_found = True
    
    # Verify at least one entity endpoint was found
    assert expected_found, "No entity routes detected! Router may not be included."
