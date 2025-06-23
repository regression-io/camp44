"""Test OIDC authentication endpoints."""

from unittest.mock import patch, MagicMock
import uuid

import pytest
from fastapi.testclient import TestClient

from camp44.main import app
from camp44.core.config import settings


client = TestClient(app)


@pytest.fixture
def mock_oauth():
    """Fixture to mock the OAuth client."""
    with patch("camp44.api.v1.oidc.oauth") as mock_oauth:
        # Create a mock oidc client
        mock_oidc = MagicMock()
        mock_oauth.oidc = mock_oidc
        yield mock_oidc


@pytest.fixture
def enable_oauth():
    """Temporarily enable OAuth for tests."""
    original_value = settings.OAUTH_ENABLED
    settings.OAUTH_ENABLED = True
    yield
    settings.OAUTH_ENABLED = original_value


def test_oidc_login_disabled():
    """Test OIDC login endpoint when OIDC is disabled."""
    response = client.get("/api/v1/auth/oidc/login")
    assert response.status_code == 501
    assert "OIDC authentication not configured" in response.json()["detail"]


def test_oidc_callback_disabled():
    """Test OIDC callback endpoint when OIDC is disabled."""
    response = client.get("/api/v1/auth/oidc/callback")
    assert response.status_code == 501
    assert "OIDC authentication not configured" in response.json()["detail"]


def test_oidc_login_redirect(mock_oauth, enable_oauth):
    """Test OIDC login redirects to provider."""
    # Set up mock
    mock_oauth.authorize_redirect.return_value = Response(
        status_code=302,
        headers={"Location": "https://example.com/oauth/authorize"}
    )
    
    # Make request
    response = client.get("/api/v1/auth/oidc/login")
    
    # Verify redirect
    assert response.status_code == 302
    assert "https://example.com/oauth/authorize" in response.headers["Location"]
    
    # Verify mock was called
    mock_oauth.authorize_redirect.assert_called_once()


@patch("camp44.api.v1.oidc.create_access_token")
@patch("camp44.api.v1.oidc.user_crud")
def test_oidc_callback_new_user(mock_user_crud, mock_create_token, mock_oauth, enable_oauth):
    """Test OIDC callback creates new user if not exists."""
    # Set up mocks
    mock_oauth.authorize_access_token.return_value = {
        "userinfo": {
            "sub": "oidc123",
            "email": "oidcuser@example.com",
            "email_verified": True,
            "name": "OIDC User",
            "tenant_id": "tenant123"
        }
    }
    
    mock_user_crud.get_by_oidc_sub.return_value = None
    mock_user_crud.get_by_email.return_value = None
    
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user_crud.create_oidc_user.return_value = mock_user
    
    mock_create_token.return_value = "fake_access_token"
    
    # Make request
    response = client.get("/api/v1/auth/oidc/callback")
    
    # Verify redirects with token
    assert response.status_code == 307  # Temporary redirect
    assert "token=fake_access_token" in response.headers["Location"]
    
    # Verify mocks called correctly
    mock_oauth.authorize_access_token.assert_called_once()
    mock_user_crud.get_by_oidc_sub.assert_called_once_with(mock.ANY, oidc_sub="oidc123")
    mock_user_crud.create_oidc_user.assert_called_once()
    mock_create_token.assert_called_once()


@patch("camp44.api.v1.oidc.create_access_token")
@patch("camp44.api.v1.oidc.user_crud")
def test_oidc_callback_existing_user(mock_user_crud, mock_create_token, mock_oauth, enable_oauth):
    """Test OIDC callback finds existing user by OIDC sub."""
    # Set up mocks
    mock_oauth.authorize_access_token.return_value = {
        "userinfo": {
            "sub": "oidc123",
            "email": "oidcuser@example.com",
            "email_verified": True,
            "name": "OIDC User",
            "tenant_id": "tenant123"
        }
    }
    
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user_crud.get_by_oidc_sub.return_value = mock_user
    
    mock_create_token.return_value = "fake_access_token"
    
    # Make request
    response = client.get("/api/v1/auth/oidc/callback")
    
    # Verify redirects with token
    assert response.status_code == 307  # Temporary redirect
    assert "token=fake_access_token" in response.headers["Location"]
    
    # Verify mocks called correctly
    mock_oauth.authorize_access_token.assert_called_once()
    mock_user_crud.get_by_oidc_sub.assert_called_once_with(mock.ANY, oidc_sub="oidc123")
    mock_user_crud.create_oidc_user.assert_not_called()  # Should not create new user
    mock_create_token.assert_called_once()


# Helper class for response mocking
class Response:
    def __init__(self, status_code, headers=None, content=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.content = content
        
    def json(self):
        return self.content
