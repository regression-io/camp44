import uuid
import traceback
import logging
import sys
import os
from typing import Dict

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, routing
from camp44.models import User, App
from camp44.main import app as fastapi_app

# Configure logging to stdout for maximum visibility
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Monkey patch FastAPI to log all requests
def log_route(route_handler):
    def wrapped_route(*args, **kwargs):
        logger.info(f"ROUTE CALLED: {route_handler.__name__} with args={args}, kwargs={kwargs}")
        try:
            return route_handler(*args, **kwargs)
        except Exception as e:
            logger.error(f"ROUTE ERROR in {route_handler.__name__}: {str(e)}")
            traceback.print_exc()
            raise
    return wrapped_route

# Apply logging to all routes
for route in fastapi_app.routes:
    if hasattr(route, "endpoint"):
        original_endpoint = route.endpoint
        route.endpoint = log_route(original_endpoint)


def test_entity_routes_debug(client: TestClient, test_user: User, test_app: App) -> None:
    """Debug entity routes specifically."""
    try:
        # Print test configuration
        logger.info(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")
        logger.info(f"Test user: {test_user.id} ({test_user.email})")
        logger.info(f"Test app: {test_app.id} ({test_app.name})")
        
        # Print entity-related routes
        logger.info("ENTITY ROUTES:")
        for route in fastapi_app.routes:
            if hasattr(route, "path") and "entities" in route.path:
                logger.info(f"Path: {route.path}, Methods: {route.methods if hasattr(route, 'methods') else 'N/A'}")
                if hasattr(route, "endpoint"):
                    logger.info(f"  Endpoint: {route.endpoint.__name__ if hasattr(route.endpoint, '__name__') else str(route.endpoint)}")
                    
        # Try simple GET first to make sure authentication works
        logger.info("Testing GET /api/v1/apps/ first")
        response = client.get("/api/v1/apps/")
        logger.info(f"GET apps status: {response.status_code}")
        logger.info(f"GET apps response: {response.text[:200]}...")
        
        # Try entity operations
        entity_name = "test_entity"
        entity_route = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        logger.info(f"Testing entity route: {entity_route}")
        
        # List entities first (should be empty but work)
        logger.info("Listing entities (GET)")
        response = client.get(entity_route)
        logger.info(f"GET entity list status: {response.status_code}")
        logger.info(f"GET entity list response: {response.text[:200]}")
        
        # Try to create an entity
        entity_data = {
            "name": entity_name,
            "data": {
                "field1": "value1"
            }
        }
        
        logger.info(f"Attempting to create entity with payload: {entity_data}")
        response = client.post(entity_route, json=entity_data)
        logger.info(f"POST entity status: {response.status_code}")
        logger.info(f"POST entity response: {response.text}")
        
        # If entity creation worked, try to get it
        if response.status_code == 200:
            entity_id = response.json().get("id")
            if entity_id:
                logger.info(f"Created entity with ID: {entity_id}, attempting to retrieve it")
                get_response = client.get(f"{entity_route}/{entity_id}")
                logger.info(f"GET entity status: {get_response.status_code}")
                logger.info(f"GET entity response: {get_response.text}")
        
    except Exception as e:
        logger.error(f"Exception during test: {str(e)}")
        logger.error("Full traceback:")
        traceback.print_exc()
        raise
