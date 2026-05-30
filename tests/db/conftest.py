"""
Local conftest — isolates engine/pool tests from the postgres+alembic autouse fixture.

The top-level ``tests/conftest.py`` has a session-scoped autouse fixture that
creates a local Postgres ``camp44_test`` DB and runs ``alembic upgrade head``
(currently broken on a pre-existing ``sqlmodel.sql.sqltypes.GUID`` migration
issue). The engine-config tests here are pure logic and need no database, so we
override that fixture with a no-op — same pattern as ``tests/rate_limit``.
"""

import os

import pytest

os.environ["TESTING"] = "1"


@pytest.fixture(scope="session", autouse=True)
def test_engine():
    """No-op override of the parent conftest's postgres+alembic setup."""
    yield None
