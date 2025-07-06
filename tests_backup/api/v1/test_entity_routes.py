"""Test file to directly examine FastAPI routes."""
import logging
import sys
import traceback
import inspect
import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from camp44.models import User, App
from camp44.main import app as fastapi_app

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_examine_routes():
    """Test that specifically examines all routes to identify entity routes."""
    try:
        # Count how many entity routes we have
        entity_routes = []
        total_routes = 0
        
        for route in fastapi_app.routes:
            total_routes += 1
            
            if hasattr(route, "path") and "entities" in route.path:
                entity_routes.append(route)
                logger.info(f"Found entity route: {route.path}")
                
                # Print detailed info about this route
                if hasattr(route, "endpoint"):
                    endpoint_name = getattr(route.endpoint, "__name__", str(route.endpoint))
                    logger.info(f"  Endpoint name: {endpoint_name}")
                    
                    # Get the module where this endpoint is defined
                    try:
                        module = inspect.getmodule(route.endpoint)
                        logger.info(f"  Module: {module.__name__ if module else 'Unknown'}")
                    except Exception as e:
                        logger.info(f"  Error getting module: {e}")
                
                # Print HTTP methods
                methods = getattr(route, "methods", set())
                logger.info(f"  Methods: {methods}")
        
        logger.info(f"Total routes: {total_routes}")
        logger.info(f"Entity routes: {len(entity_routes)}")
        
    except Exception as e:
        logger.error(f"Exception: {e}")
        traceback.print_exc()
        raise

def test_manual_endpoint_call(client: TestClient, test_user: User, test_app: App):
    """Attempt to call entity endpoints manually, bypassing router mechanisms."""
    try:
        # Confirm test fixtures are valid
        logger.info(f"Test user: {test_user.id} ({test_user.email})")
        logger.info(f"Test app: {test_app.id} ({test_app.name})")
        
        # Test basic app endpoint first
        response = client.get("/api/v1/apps/")
        logger.info(f"Apps endpoint status: {response.status_code}")
        
        entity_name = "test_entity"
        
        # Try each entity endpoint manually
        endpoints = [
            # (method, path, data)
            ("GET", f"/api/v1/apps/{test_app.id}/entities/{entity_name}", None),
            ("POST", f"/api/v1/apps/{test_app.id}/entities/{entity_name}", 
             {"name": entity_name, "data": {"field": "value"}}),
            ("GET", f"/api/v1/apps/{test_app.id}/entities/{entity_name}/fake-id", None),
            ("POST", f"/api/v1/apps/{test_app.id}/entities/{entity_name}/filter", 
             {"field": "value"}),
        ]
        
        for method, path, data in endpoints:
            try:
                logger.info(f"Testing {method} {path}")
                
                if method == "GET":
                    response = client.get(path)
                elif method == "POST":
                    response = client.post(path, json=data)
                
                logger.info(f"  Status: {response.status_code}")
                logger.info(f"  Response: {response.text[:200]}")
                
            except Exception as e:
                logger.error(f"Error with {method} {path}: {e}")
                
    except Exception as e:
        logger.error(f"Exception: {e}")
        traceback.print_exc()
        raise
