"""Test WebAuthn/Passkey authentication endpoints."""

import base64
import uuid
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from camp44.main import app
from camp44.models.user import User

client = TestClient(app)


@pytest.fixture
def mock_user():
    """Fixture to create a mock authenticated user."""
    user_id = uuid.uuid4()
    mock_user = User(
        id=user_id,
        email="testuser@example.com",
        display_name="Test User",
        hashed_password="fakehash",
        is_active=True,
        roles=["user"],
        passkey_credentials=[]
    )
    return mock_user


@pytest.fixture
def mock_db_session():
    """Fixture to mock the database session."""
    with patch("camp44.api.deps.get_db") as mock_get_db:
        mock_session = MagicMock(spec=Session)
        # Create sync context manager
        mock_get_db.return_value = mock_session
        yield mock_session


@pytest.fixture
def auth_headers():
    """Fixture to provide authentication headers."""
    with patch("camp44.api.deps.get_current_active_user") as mock_get_user:
        user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = user_id
        mock_user.email = "testuser@example.com"
        mock_user.display_name = "Test User"
        mock_user.passkey_credentials = []
        mock_get_user.return_value = mock_user

        yield {"Authorization": "Bearer fake_token"}


@pytest.mark.skip(reason="Authentication flow needs proper mocking in synchronous environment")
@patch("camp44.api.v1.passkey.generate_passkey_registration_options")
def test_passkey_register_options(mock_generate_options, auth_headers, mock_user):
    """Test getting passkey registration options."""
    # Mock the options generation
    mock_options = MagicMock()
    mock_options.challenge = b"fake_challenge"
    mock_options.model_dump.return_value = {
        "challenge": "fake_challenge_base64",
        "rp": {"id": "localhost", "name": "Camp44"},
        "user": {
            "id": str(mock_user.id),
            "name": mock_user.email,
            "displayName": mock_user.display_name
        },
        "pubKeyCredParams": [{"alg": -7, "type": "public-key"}],
        "timeout": 60000
    }
    mock_generate_options.return_value = mock_options

    # Make request
    response = client.post(
        "/api/v1/auth/passkey/register/options",
        json={"user_id": str(mock_user.id)},
        headers=auth_headers
    )

    # Verify response
    assert response.status_code == 200
    assert "options" in response.json()
    assert response.json()["options"]["challenge"] is not None


@pytest.mark.skip(reason="Authentication flow needs proper mocking in synchronous environment")
@patch("camp44.api.v1.passkey.verify_passkey_registration")
@patch("camp44.crud.user.update_user")
def test_passkey_register_verify(mock_update, mock_verify, auth_headers, mock_db_session):
    """Test verifying passkey registration."""
    # Set up the test data
    user_id = str(uuid.uuid4())
    fake_credential = {
        "id": "credential123",
        "rawId": base64.b64encode(b"rawId123").decode("ascii"),
        "response": {
            "attestationObject": base64.b64encode(b"attestation").decode("ascii"),
            "clientDataJSON": base64.b64encode(b"clientData").decode("ascii")
        },
        "type": "public-key"
    }

    # Set up mocks
    mock_verify.return_value = {
        "id": "credential123",
        "public_key": base64.b64encode(b"publicKey").decode("ascii"),
        "sign_count": 0
    }

    # Store fake challenge
    with patch.dict("camp44.api.v1.passkey._CHALLENGES", {user_id: "fake_challenge"}):
        # Make request
        response = client.post(
            "/api/v1/auth/passkey/register/verify",
            json={"user_id": user_id, "credential": fake_credential},
            headers=auth_headers
        )

        # Verify response
        assert response.status_code == 200
        assert response.json()["success"] is True
        assert response.json()["credential_id"] == "credential123"

        # Verify mocks called correctly
        mock_verify.assert_called_once()
        mock_update.assert_called_once()


@patch("camp44.api.v1.passkey.generate_passkey_authentication_options")
@patch("camp44.crud.user.get_user_by_email")
def test_passkey_authenticate_options(mock_get_by_email, mock_generate_options):
    """Test getting passkey authentication options."""
    # Set up mocks
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.passkey_credentials = [{"id": "credential123"}]
    mock_get_by_email.return_value = mock_user

    mock_options = MagicMock()
    mock_options.challenge = b"fake_challenge"
    mock_options.model_dump.return_value = {
        "challenge": "fake_challenge_base64",
        "rpId": "localhost",
        "allowCredentials": [{"type": "public-key", "id": "credential123"}],
        "timeout": 60000
    }
    mock_generate_options.return_value = mock_options

    # Make request
    response = client.post(
        "/api/v1/auth/passkey/authenticate/options",
        json={"email": "testuser@example.com"}
    )

    # Verify response
    assert response.status_code == 200
    assert "options" in response.json()
    assert response.json()["options"]["challenge"] is not None


@pytest.mark.skip(reason="Authentication flow needs proper mocking in synchronous environment")
@patch("camp44.api.v1.passkey.verify_passkey_authentication")  
@patch("camp44.crud.user.update_user")
@patch("camp44.crud.user.get_user_by_email")
@patch("camp44.api.v1.passkey.create_access_token")
def test_passkey_authenticate_verify(mock_create_token, mock_get_by_email, mock_update, mock_verify):
    """Test verifying passkey authentication."""
    # Set up the test data
    user_id = str(uuid.uuid4())
    fake_credential = {
        "id": "credential123",
        "rawId": base64.b64encode(b"rawId123").decode("ascii"),
        "response": {
            "authenticatorData": base64.b64encode(b"authData").decode("ascii"),
            "clientDataJSON": base64.b64encode(b"clientData").decode("ascii"),
            "signature": base64.b64encode(b"signature").decode("ascii"),
        },
        "type": "public-key"
    }

    # Set up mocks
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_user.passkey_credentials = [
        {
            "id": "credential123",
            "public_key": base64.b64encode(b"publicKey").decode("ascii"),
            "sign_count": 0
        }
    ]
    mock_get_by_email.return_value = mock_user
    mock_verify.return_value = 1  # New sign count
    mock_create_token.return_value = "fake_jwt_token"

    # Store fake challenge
    with patch.dict("camp44.api.v1.passkey._CHALLENGES", {str(mock_user.id): "fake_challenge"}):
        # Make request
        response = client.post(
            "/api/v1/auth/passkey/authenticate/verify",
            json={"credential": fake_credential, "email": "testuser@example.com", "credential_id": "credential123"}
        )

        # Verify response
        assert response.status_code == 200
        assert response.json()["access_token"] == "fake_jwt_token"
        assert response.json()["token_type"] == "bearer"

        # Verify mocks called correctly
        mock_verify.assert_called_once()
        mock_update.assert_called_once()
        mock_create_token.assert_called_once_with(data={"sub": str(mock_user.id)})
