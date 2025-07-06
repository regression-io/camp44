"""Deep debugging test for entity router registration issues."""

import inspect
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def test_entity_router_deep_debug(app: FastAPI) -> None:
    """Deeply investigate router registration issues with entity endpoints."""
    print("\n=== DEEP DEBUGGING ENTITY ROUTER REGISTRATION ===")
    
    # DETAILED MAIN APP INSPECTION
    print("\nAll registered routes in app:")
    all_routes = []
    for idx, route in enumerate(app.routes):
        if hasattr(route, "path"):
            print(f"Route {idx}: {route.path}")
        else:
            print(f"Route {idx}: <no path>")
        
        if hasattr(route, "methods"):
            methods = list(route.methods)
            print(f"  Methods: {methods}")
        
        if hasattr(route, "endpoint") and route.endpoint:
            endpoint_name = getattr(route.endpoint, "__name__", str(route.endpoint))
            print(f"  Endpoint: {endpoint_name}")
            
            # Check if this is a function from entities.py
            import inspect as inspect_module
            module = inspect_module.getmodule(route.endpoint)
            if module and "entities" in str(module):
                print(f"  ** ENTITY ENDPOINT FOUND: {endpoint_name} from {module}")
        
        # Check if this is a router with app attribute (indicates nested router)
        if hasattr(route, "app"):
            print(f"  ** Has nested app/router: {type(route.app).__name__}")
            # If this is an APIRouter mounted at /api/v1/apps/{app_id}/entities
            if hasattr(route, "path") and "{app_id}" in route.path and "entities" in route.path:
                print(f"  ** ENTITY ROUTER FOUND at {route.path}")
    
    # IMPORTED APP INSPECTION
    print("\nChecking entity router registration in main.py:")
    from camp44.main import app as main_app
    
    # Check for router include statements
    import inspect
    import camp44.main
    main_source = inspect.getsource(camp44.main)
    print("\nRouter include statements in main.py:")
    for line in main_source.split("\n"):
        if "include_router" in line and "entities" in line:
            print(f"FOUND ENTITY ROUTER INCLUDE: {line.strip()}")
    
    # Check if entities module has router
    print("\nChecking entity router definition:")
    from camp44.api.v1.endpoints import entities
    has_router = hasattr(entities, 'router')
    print(f"Entity router exists in module: {has_router}")
    
    if has_router:
        # Inspect entity router
        print(f"\nEntity router inspection:")
        router = entities.router
        print(f"Router type: {type(router).__name__}")
        print(f"Router routes count: {len(router.routes)}")
        
        # Print all routes in entity router
        print("Entity router routes:")
        for idx, route in enumerate(router.routes):
            if hasattr(route, "path"):
                path = route.path
            else:
                path = "<no path>"
                
            if hasattr(route, "methods"):
                methods = list(route.methods)
            else:
                methods = []
                
            if hasattr(route, "endpoint") and route.endpoint:
                endpoint = getattr(route.endpoint, "__name__", str(route.endpoint))
            else:
                endpoint = "<no endpoint>"
                
            print(f"  Route {idx}: {methods} {path} -> {endpoint}")
    
    # EXAMINE V1 API ROUTER
    print("\nChecking V1 API router:")
    from camp44.api.v1.api import api_router
    print(f"V1 API router routes count: {len(api_router.routes)}")
    
    print("\nV1 API router routes:")
    for idx, route in enumerate(api_router.routes):
        if hasattr(route, "path"):
            path = route.path
            print(f"Route {idx}: {path}")
            if "{app_id}" in path and "entities" in path:
                print(f"  ** FOUND ENTITY PATH IN V1 API: {path}")
        else:
            print(f"Route {idx}: <no path>")
    
    # CHECK ROUTER INCLUSION
    print("\nChecking router inclusion chain:")
    # Load api.py source to check entity router inclusion
    import camp44.api.v1.api
    api_source = inspect.getsource(camp44.api.v1.api)
    print("Router include statements in api.py:")
    for line in api_source.split("\n"):
        if "include_router" in line and "entities" in line:
            print(f"FOUND ENTITY ROUTER INCLUDE IN API.PY: {line.strip()}")
        elif "include_router" in line:
            print(f"Other router include: {line.strip()}")
    
    # Make sure test passes
    assert True
