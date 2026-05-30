"""
Isolate passkey/WebAuthn CBOR tests from the top-level postgres autouse fixture.

Same rationale as ``tests/rate_limit`` and ``tests/oidc``: these tests are pure
crypto/CBOR and need no DB, so the parent's (currently broken) alembic fixture is
overridden to a no-op here.
"""

import os

import pytest

os.environ["TESTING"] = "1"


@pytest.fixture(scope="session", autouse=True)
def test_engine():
    """No-op override of the parent conftest's postgres+alembic setup."""
    yield None
