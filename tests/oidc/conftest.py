"""
Isolate OIDC token-validation tests from the top-level postgres autouse fixture.

Same rationale as ``tests/rate_limit/conftest.py``: the root
``tests/conftest.py`` has a session-scoped autouse fixture that runs
``alembic upgrade head`` against a local Postgres, which currently fails on an
unrelated ``sqlmodel.sql.sqltypes.GUID`` migration issue. ``OIDCTokenValidator``
is pure crypto/claims logic and needs no DB, so we override the fixture to a
no-op and live in this subdir.
"""

import os

import pytest

os.environ["TESTING"] = "1"


@pytest.fixture(scope="session", autouse=True)
def test_engine():
    """No-op override of the parent conftest's postgres+alembic setup."""
    yield None
