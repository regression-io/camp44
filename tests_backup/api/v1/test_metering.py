from fastapi.testclient import TestClient

from camp44.models import User


def test_metering_unauthenticated(client: TestClient):
    response = client.post(
        "/api/v1/metering",
        json={"tenant_id": "1", "app_id": "1", "event_name": "test_event"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": {"code": 401, "message": "Not authenticated"}}


def test_metering_success(client: TestClient, test_user: User):
    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "testpassword"},
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/api/v1/metering",
        headers={"Authorization": f"Bearer {token}"},
        json={"tenant_id": "1", "app_id": "1", "event_name": "test_event"},
    )
    assert response.status_code == 202
    assert response.json() == {"status": "accepted"}
