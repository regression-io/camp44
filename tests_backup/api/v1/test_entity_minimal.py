import logging
import sys
import traceback
import os

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI
import inspect

from camp44.models import User, App
from camp44.main import app as fastapi_app

# Set up detailed logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Print the actual paths from the app
def log_app_routes():
    """Log all routes in the FastAPI app"""
    logger.debug("==== ALL REGISTERED ROUTES ====")
    for route in fastapi_app.routes:
        if hasattr(route, "path"):
            methods = getattr(route, "methods", set())
            logger.debug(f"Path: {route.path}, Methods: {methods}")
            if hasattr(route, "endpoint") and route.endpoint:
                try:
                    endpoint_name = route.endpoint.__name__
                    endpoint_module = inspect.getmodule(route.endpoint).__name__
                    logger.debug(f"  Endpoint: {endpoint_name} from {endpoint_module}")
                except Exception as e:
                    logger.debug(f"  Error getting endpoint info: {e}")

def test_minimal_entity_endpoint(client: TestClient, test_user: User, test_app: App) -> None:
    """Minimal test just to check if entity endpoint responds"""
    try:
        # Log app routes first
        log_app_routes()
        
        # Log key environment variables
        logger.debug(f"DATABASE_URL: {os.environ.get('DATABASE_URL', 'Not set')}")
        
        # Log test fixtures
        logger.debug(f"Test user: {test_user.id} ({test_user.email})")
        logger.debug(f"Test app: {test_app.id} ({test_app.name})")
        
        # Try a simpler endpoint first to verify the client works
        logger.debug("Testing GET /api/v1/apps/ first as sanity check")
        try:
            response = client.get("/api/v1/apps/")
            logger.debug(f"Apps endpoint status: {response.status_code}")
        except Exception as e:
            logger.error(f"Error accessing apps endpoint: {e}")
            raise
        
        # Now try the entity endpoint
        entity_name = "test_entity"
        url = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        
        logger.debug(f"Making GET request to: {url}")
        
        try:
            response = client.get(url)
            logger.debug(f"Response status code: {response.status_code}")
            logger.debug(f"Response body: {response.text[:500]}")
        except Exception as e:
            logger.error(f"Error during entity request: {e}")
            logger.error("Full error traceback:")
            traceback.print_exc()
            raise
        
    except Exception as e:
        logger.error(f"TOP LEVEL EXCEPTION: {e}")
        logger.error("Full error traceback:")
        traceback.print_exc()
        raise
