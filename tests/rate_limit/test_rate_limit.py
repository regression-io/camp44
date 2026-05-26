"""
Rate-limit tests for auth surfaces (P1-4).

These tests verify slowapi is wired and trips at the configured thresholds.
They use ``TestClient`` directly against the FastAPI app — they do NOT depend
on the postgres-backed conftest fixture, so they run even when the broader
test database isn't migrated.

The handlers will 500 (missing tables) or 400 (invalid input) on the first
N requests; we only assert the *last* requests return 429.
"""

import pytest
from fastapi.testclient import TestClient

from camp44.core.rate_limit import limiter
from camp44.main import app


@pytest.fixture
def client():
    """Fresh TestClient with limiter enabled and counter reset."""
    limiter.reset()
    limiter.enabled = True
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        limiter.enabled = False
        limiter.reset()


def _hammer(client, method, url, **kwargs):
    """Send ``count`` requests and return status codes."""
    return [
        getattr(client, method)(url, **kwargs).status_code
        for _ in range(kwargs.pop("count", 1))
    ]


def test_login_rate_limited_at_10_per_minute(client):
    payload = {"username": "ghost@example.com", "password": "wrong"}
    statuses = [client.post("/auth/login", data=payload).status_code for _ in range(12)]
    assert statuses[-1] == 429, f"Expected 429 on 12th call, got {statuses}"
    assert statuses[-2] == 429
    assert statuses[:10].count(429) == 0, f"First 10 should not be 429: {statuses}"


def test_forgot_password_rate_limited_at_5_per_minute(client):
    payload = {"email": "ghost@example.com"}
    statuses = [
        client.post("/auth/forgot-password", json=payload).status_code for _ in range(7)
    ]
    assert statuses[-1] == 429, f"Expected 429 on 7th call, got {statuses}"
    assert statuses[:5].count(429) == 0


def test_set_password_rate_limited_at_10_per_minute(client):
    payload = {"token": "no-such-token", "password": "longenoughpw"}
    statuses = [
        client.post("/auth/set-password", json=payload).status_code for _ in range(12)
    ]
    assert statuses[-1] == 429, f"Expected 429 on 12th call, got {statuses}"


def test_passkey_authenticate_options_rate_limited(client):
    payload = {"email": "ghost@example.com"}
    statuses = [
        client.post("/auth/passkey/authenticate/options", json=payload).status_code
        for _ in range(12)
    ]
    assert statuses[-1] == 429, f"Expected 429 on 12th call, got {statuses}"


def test_passkey_authenticate_verify_rate_limited(client):
    payload = {
        "credential_id": "fake",
        "credential": {"id": "x", "rawId": "x", "response": {}, "type": "public-key"},
        "email": "ghost@example.com",
    }
    statuses = [
        client.post("/auth/passkey/authenticate/verify", json=payload).status_code
        for _ in range(12)
    ]
    assert statuses[-1] == 429, f"Expected 429 on 12th call, got {statuses}"
