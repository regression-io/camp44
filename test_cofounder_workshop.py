#!/usr/bin/env python3
"""
Test script for cofounder workshop functionality against running service.
"""

import json
import requests
from typing import Dict, Any, Optional
import uuid
import sys
import time

# Configuration
API_BASE = "http://localhost:8000/api/v1"
TEST_USER = "test@cofounder.workshop"
TEST_PASSWORD = "testpassword123"
APP_NAME = f"Cofounder Workshop App {uuid.uuid4()}"
DEBUG = True  # Set to True for detailed debugging output

class APIClient:
    """Simple API client for testing the cofounder workshop project."""
    
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.token = None
        self.headers = {"Content-Type": "application/json"}
        self.app_id = None
        
    def debug_request(self, method, url, data=None, resp=None):
        """Print debug information about a request."""
        if DEBUG:
            print(f"\n🔍 DEBUG: {method} {url}")
            if data:
                print(f"🔍 Request data: {json.dumps(data)}")
            if resp:
                print(f"🔍 Status: {resp.status_code}")
                try:
                    print(f"🔍 Response: {json.dumps(resp.json(), indent=2)}")
                except:
                    print(f"🔍 Raw response: {resp.text}")
            print()
                
    def register(self, email: str, password: str, display_name: str = "Test User") -> Dict[str, Any]:
        """Register a new user."""
        url = f"{self.base_url}/auth/register"
        payload = {
            "email": email,
            "password": password,
            "display_name": display_name
        }
        response = requests.post(url, json=payload)
        print(f"➡️ Register user: {email}")
        self.debug_request("POST", url, payload, response)
        
        if response.status_code == 200:
            print(f"✅ User registered successfully")
            return response.json()
        else:
            print(f"❌ Registration failed: {response.status_code} - {response.text}")
            return {}
    
    def login(self, email: str, password: str) -> bool:
        """Login and get authentication token."""
        url = f"{self.base_url}/auth/login"
        data = {
            "username": email,  # OAuth2 form field is 'username' even though we use email
            "password": password
        }
        response = requests.post(url, data=data)
        print(f"➡️ Login: {email}")
        self.debug_request("POST", url, data, response)
        
        if response.status_code == 200:
            token_data = response.json()
            self.token = token_data["access_token"]
            self.headers["Authorization"] = f"Bearer {self.token}"
            print(f"✅ Login successful, token: {self.token[:10]}...")
            return True
        else:
            print(f"❌ Login failed: {response.status_code} - {response.text}")
            return False
    
    def create_app(self, name: str) -> Optional[Dict[str, Any]]:
        """Create a new application."""
        url = f"{self.base_url}/apps"
        payload = {"name": name}
        response = requests.post(url, json=payload, headers=self.headers)
        print(f"➡️ Create app: {name}")
        self.debug_request("POST", url, payload, response)
        
        if response.status_code in [200, 201]:
            app_data = response.json()
            self.app_id = app_data['id']  # Store app_id for future requests
            print(f"✅ App created: {app_data['id']}")
            return app_data
        else:
            print(f"❌ App creation failed: {response.status_code} - {response.text}")
            return None
    
    def list_apps(self) -> list:
        """List all applications."""
        url = f"{self.base_url}/apps"
        response = requests.get(url, headers=self.headers)
        print("➡️ List apps")
        self.debug_request("GET", url, None, response)
        
        if response.status_code == 200:
            apps = response.json()
            print(f"✅ Found {len(apps)} apps")
            for app in apps:
                print(f"  - {app['name']} ({app['id']})")
                self.app_id = app['id']  # Store the last app_id
            return apps
        else:
            print(f"❌ List apps failed: {response.status_code} - {response.text}")
            return []
    
    def get_app(self, app_id: str) -> Optional[Dict[str, Any]]:
        """Get app details by ID."""
        url = f"{self.base_url}/apps/{app_id}"
        response = requests.get(url, headers=self.headers)
        print(f"➡️ Get app: {app_id}")
        self.debug_request("GET", url, None, response)
        
        if response.status_code == 200:
            app = response.json() 
            print(f"✅ App found: {app['name']}")
            return app
        else:
            print(f"❌ App not found: {response.status_code} - {response.text}")
            return None
    
    def create_entity(self, entity_name: str, entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a new entity."""
        if not self.app_id:
            print("❌ No app_id available. Call create_app or list_apps first.")
            return None
            
        url = f"{self.base_url}/apps/{self.app_id}/entities/{entity_name}"
        payload = {"data": entity_data, "name": entity_name}
        response = requests.post(url, json=payload, headers=self.headers)
        print(f"➡️ Create entity: {entity_name}")
        self.debug_request("POST", url, payload, response)
        
        if response.status_code == 201:
            entity = response.json()
            print(f"✅ Entity created: {entity['id']}")
            return entity
        else:
            print(f"❌ Entity creation failed: {response.status_code} - {response.text}")
            return None
    
    def get_entities(self, entity_name: str) -> list:
        """List entities of a specific type."""
        if not self.app_id:
            print("❌ No app_id available. Call create_app or list_apps first.")
            return []
            
        url = f"{self.base_url}/apps/{self.app_id}/entities/{entity_name}"
        response = requests.get(url, headers=self.headers)
        print(f"➡️ Get entities: {entity_name}")
        self.debug_request("GET", url, None, response)
        
        if response.status_code == 200:
            entities = response.json()
            print(f"✅ Found {len(entities)} {entity_name} entities")
            return entities
        else:
            print(f"❌ Get entities failed: {response.status_code} - {response.text}")
            return []
    
    def filter_entities(self, entity_name: str, filters: Dict[str, Any]) -> list:
        """Filter entities by criteria."""
        if not self.app_id:
            print("❌ No app_id available. Call create_app or list_apps first.")
            return []
            
        url = f"{self.base_url}/apps/{self.app_id}/entities/{entity_name}/filter"
        payload = {"filters": filters}
        response = requests.post(url, json=payload, headers=self.headers)
        print(f"➡️ Filter {entity_name} by {json.dumps(filters)}")
        self.debug_request("POST", url, payload, response)
        
        if response.status_code == 200:
            entities = response.json()
            print(f"✅ Found {len(entities)} matching entities")
            return entities
        else:
            print(f"❌ Filter entities failed: {response.status_code} - {response.text}")
            return []
    
    def update_entity(self, entity_name: str, entity_id: str, entity_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Update an entity."""
        if not self.app_id:
            print("❌ No app_id available. Call create_app or list_apps first.")
            return None
            
        url = f"{self.base_url}/apps/{self.app_id}/entities/{entity_name}/{entity_id}"
        payload = {"data": entity_data}
        response = requests.patch(url, json=payload, headers=self.headers)
        print(f"➡️ Update entity: {entity_name}/{entity_id}")
        self.debug_request("PATCH", url, payload, response)
        
        if response.status_code == 200:
            entity = response.json()
            print(f"✅ Entity updated: {entity['id']}")
            return entity
        else:
            print(f"❌ Entity update failed: {response.status_code} - {response.text}")
            return None
    
    def delete_entity(self, entity_name: str, entity_id: str) -> bool:
        """Delete an entity."""
        if not self.app_id:
            print("❌ No app_id available. Call create_app or list_apps first.")
            return False
            
        url = f"{self.base_url}/apps/{self.app_id}/entities/{entity_name}/{entity_id}"
        response = requests.delete(url, headers=self.headers)
        print(f"➡️ Delete entity: {entity_name}/{entity_id}")
        self.debug_request("DELETE", url, None, response)
        
        if response.status_code == 204:
            print(f"✅ Entity deleted")
            return True
        else:
            print(f"❌ Entity deletion failed: {response.status_code} - {response.text}")
            return False


def run_cofounder_workshop_test():
    """Test the cofounder workshop functionality."""
    client = APIClient(API_BASE)
    
    # Step 1: Register or login
    try:
        client.register(TEST_USER, TEST_PASSWORD)
    except Exception as e:
        print(f"Registration error (expected if user exists): {e}")
    
    # Try to login
    if not client.login(TEST_USER, TEST_PASSWORD):
        print("Cannot continue without login")
        sys.exit(1)
    
    # Step 2: Create an app for the workshop or find existing
    apps = client.list_apps()
    
    if not apps:
        # Create a new app if none exist
        app = client.create_app(APP_NAME)
        if not app:
            print("Cannot continue without app")
            sys.exit(1)
            
        # Give the database a moment to complete the transaction
        print("Waiting for app creation to be fully committed...")
        time.sleep(2)
    
    print(f"\n=== Using App: {APP_NAME} (ID: {client.app_id}) ===\n")
    
    # Step 3: Create founder profiles
    founders = [
        {
            "name": "Alice Johnson",
            "email": "alice@startupventure.com",
            "role": "CEO",
            "skills": ["leadership", "fundraising", "product strategy"],
            "experience": 8,
            "linkedin": "https://linkedin.com/in/alice-johnson"
        },
        {
            "name": "Bob Smith",
            "email": "bob@startupventure.com",
            "role": "CTO",
            "skills": ["software architecture", "cloud infrastructure", "AI/ML"],
            "experience": 10,
            "linkedin": "https://linkedin.com/in/bob-smith"
        }
    ]
    
    # Create founder entities
    created_founders = []
    for founder in founders:
        result = client.create_entity("founder", founder)
        if result:
            created_founders.append(result)
    
    # Step 4: Create startup info
    startup = {
        "name": "InnovateTech",
        "description": "AI-powered SaaS platform for predictive analytics",
        "industry": "Technology",
        "stage": "Seed",
        "founding_date": "2024-01-15"
    }
    
    startup_entity = client.create_entity("startup", startup)
    
    # Step 5: Create milestone entities
    milestones = [
        {
            "title": "MVP Launch",
            "description": "Launch minimum viable product to early adopters",
            "target_date": "2024-08-30",
            "status": "In Progress",
            "priority": "High"
        },
        {
            "title": "Seed Funding",
            "description": "Secure $1M in seed funding",
            "target_date": "2024-10-15",
            "status": "Not Started",
            "priority": "Critical"
        }
    ]
    
    created_milestones = []
    for milestone in milestones:
        result = client.create_entity("milestone", milestone)
        if result:
            created_milestones.append(result)
    
    # Step 6: Test filtering capabilities
    print("\n=== Testing filtering capabilities ===")
    high_priority = client.filter_entities("milestone", {"priority": "High"})
    print(f"High priority milestones: {len(high_priority)}")
    
    cto_founders = client.filter_entities("founder", {"role": "CTO"})
    print(f"CTO founders: {len(cto_founders)}")
    
    # Step 7: Update a milestone if any were created
    if created_milestones:
        milestone_to_update = created_milestones[0]
        updated_data = milestone_to_update["data"].copy()
        updated_data["status"] = "Completed"
        updated_milestone = client.update_entity(
            "milestone", milestone_to_update["id"], updated_data
        )
        
        # Verify update
        if updated_milestone and updated_milestone["data"]["status"] == "Completed":
            print("✅ Milestone status updated successfully")
        else:
            print("❌ Milestone update verification failed")
    
    # Step 8: List all data for verification
    print("\n=== Final Data Verification ===")
    all_founders = client.get_entities("founder")
    all_milestones = client.get_entities("milestone")
    
    print(f"Total founders: {len(all_founders)}")
    print(f"Total milestones: {len(all_milestones)}")


if __name__ == "__main__":
    print("=== Starting Cofounder Workshop Test ===")
    run_cofounder_workshop_test()
    print("\n=== Test Completed ===")
