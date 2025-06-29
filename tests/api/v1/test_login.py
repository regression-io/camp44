from fastapi.testclient import TestClient
from sqlmodel import Session

from camp44.models.user import User


def test_login(client: TestClient, test_user: User):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "testpassword"},
    )
    assert response.status_code == 200
    token = response.json()
    assert "access_token" in token
    assert token["token_type"] == "bearer"


def test_login_wrong_password(client: TestClient, test_user: User):
    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "wrongpassword"},
    )
    assert response.status_code == 401
    assert response.json() == {"error": {"code": 401, "message": "Incorrect email or password"}}


def test_login_inactive_user(client: TestClient, db_session: Session, test_user: User):
    test_user.is_active = False
    db_session.add(test_user)
    db_session.commit()

    response = client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "testpassword"},
    )
    assert response.status_code == 400
    assert response.json() == {"error": {"code": 400, "message": "Inactive user"}}
