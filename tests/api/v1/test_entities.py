import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44.models.user import User
from camp44.models.app import App


class TestEntityEndpoints:
    """Test endpoints for entity management."""

    def test_create_read_update_delete_entity(
            self, client: TestClient, test_user: User, test_app: App
    ) -> None:
        """Test the complete CRUD cycle for an entity."""
        # Print debug info
        print(f"\nTEST DEBUG - User ID: {test_user.id}, Email: {test_user.email}")
        print(f"TEST DEBUG - App ID: {test_app.id}, Name: {test_app.name}")

        entity_name = "customer"
        entity_data = {
            "name": entity_name,
            "data": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com"
            }
        }

        # Create entity
        print(f"TEST DEBUG - Creating entity with URL: /api/v1/apps/{test_app.id}/entities/{entity_name}")
        print(f"TEST DEBUG - Entity payload: {entity_data}")
        response = client.post(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}",
            json=entity_data
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200, f"Error creating entity: {response.text}"

        created_entity = response.json()
        print(f"TEST DEBUG - Created entity: {created_entity}")
        assert created_entity["name"] == entity_name
        assert created_entity["data"]["first_name"] == "John"
        assert created_entity["app_id"] == str(test_app.id)
        entity_id = created_entity["id"]

        # Read entity by ID
        response = client.get(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}"
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200
        entity = response.json()
        print(f"TEST DEBUG - Retrieved entity: {entity}")
        assert entity["id"] == entity_id
        assert entity["name"] == entity_name
        assert entity["data"]["email"] == "john.doe@example.com"

        # List all entities
        response = client.get(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200
        entities = response.json()
        print(f"TEST DEBUG - Retrieved entities: {entities}")
        assert len(entities) >= 1
        assert any(e["id"] == entity_id for e in entities)

        # Filter entities
        filter_payload = {"filters": {"email": "john.doe@example.com"}}
        response = client.post(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}/filter",
            json=filter_payload
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200
        filtered_entities = response.json()
        print(f"TEST DEBUG - Filtered entities: {filtered_entities}")
        assert len(filtered_entities) >= 1
        assert any(e["id"] == entity_id for e in filtered_entities)

        # Update entity
        update_data = {
            "data": {
                "first_name": "Jane",
                "last_name": "Doe",
                "email": "jane.doe@example.com"
            }
        }
        response = client.patch(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}",
            json=update_data
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200
        updated_entity = response.json()
        print(f"TEST DEBUG - Updated entity: {updated_entity}")
        assert updated_entity["id"] == entity_id
        assert updated_entity["data"]["first_name"] == "Jane"
        assert updated_entity["data"]["email"] == "jane.doe@example.com"

        # Delete entity
        response = client.delete(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}"
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200
        assert response.json()["ok"] is True

        # Verify deletion
        response = client.get(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}"
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 404

    def test_entity_permission_checks(self, client: TestClient, test_app: App, unauthorized_client: TestClient) -> None:
        """Test that entity operations are properly secured"""
        entity_name = "product"
        entity_data = {
            "name": entity_name,
            "data": {
                "title": "Test Product",
                "price": 99.99
            }
        }

        # Create entity as authorized user
        response = client.post(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}",
            json=entity_data
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 200
        entity_id = response.json()["id"]

        # Attempt unauthorized access
        endpoints = [
            # (method, path, data, expected status)
            ("GET", f"/api/v1/apps/{test_app.id}/entities/{entity_name}", None, 401),
            ("GET", f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}", None, 401),
            ("POST", f"/api/v1/apps/{test_app.id}/entities/{entity_name}", entity_data, 401),
            ("POST", f"/api/v1/apps/{test_app.id}/entities/{entity_name}/filter", {"price": 99.99}, 401),
            ("PATCH", f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}", {"data": {"price": 79.99}}, 401),
            ("DELETE", f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{entity_id}", None, 401),
        ]

        for method, path, data, expected_status in endpoints:
            if method == "GET":
                response = unauthorized_client.get(path)
            elif method == "POST":
                response = unauthorized_client.post(path, json=data)
            elif method == "PATCH":
                response = unauthorized_client.patch(path, json=data)
            elif method == "DELETE":
                response = unauthorized_client.delete(path)

            print(f"TEST DEBUG - Response status: {response.status_code}")
            print(f"TEST DEBUG - Response body: {response.text}")
            assert response.status_code == expected_status, f"{method} {path} should return {expected_status}, got {response.status_code} instead."

    def test_entity_validation(self, client: TestClient, test_app: App) -> None:
        """Test validation scenarios for entity operations"""
        # Test entity with name mismatch
        entity_name = "product"
        entity_data = {
            "name": "mismatched_name",  # Doesn't match the URL path
            "data": {
                "title": "Test Product"
            }
        }

        response = client.post(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}",
            json=entity_data
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 400

        # Test with wrong app ID
        fake_app_id = str(uuid.uuid4())
        response = client.post(
            f"/api/v1/apps/{fake_app_id}/entities/{entity_name}",
            json={"name": entity_name, "data": {"title": "Test Product"}}
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 404

        # Test access to non-existent entity
        fake_entity_id = str(uuid.uuid4())
        response = client.get(
            f"/api/v1/apps/{test_app.id}/entities/{entity_name}/{fake_entity_id}"
        )
        print(f"TEST DEBUG - Response status: {response.status_code}")
        print(f"TEST DEBUG - Response body: {response.text}")
        assert response.status_code == 404

    def test_debug_entity_creation(self, client: TestClient, test_app: App) -> None:
        """Debug test to isolate entity creation issues."""
        print(f"\nDEBUG TEST - App ID: {test_app.id}, Name: {test_app.name}")
        
        # Set up the test data
        entity_name = "simple_entity"
        entity_data = {
            "name": entity_name,
            "data": {"test": "data"}
        }
        
        # Try entity creation with very detailed logging
        url = f"/api/v1/apps/{test_app.id}/entities/{entity_name}"
        print(f"DEBUG TEST - URL: {url}")
        print(f"DEBUG TEST - JSON: {entity_data}")
        
        # Make the request with exception handling
        try:
            response = client.post(url, json=entity_data)
            print(f"DEBUG TEST - Status: {response.status_code}")
            print(f"DEBUG TEST - Response: {response.text}")
            
            if response.status_code == 200:
                entity = response.json()
                print(f"DEBUG TEST - Created entity ID: {entity.get('id')}")
            else:
                print(f"DEBUG TEST - Failed with status {response.status_code}: {response.text}")
        except Exception as e:
            print(f"DEBUG TEST - Exception: {type(e).__name__}: {str(e)}")
            import traceback
            traceback.print_exc()
