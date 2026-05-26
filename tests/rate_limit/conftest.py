"""
Local conftest — isolates rate-limit tests from the top-level postgres+alembic autouse fixture.

The top-level ``tests/conftest.py`` has a session-scoped autouse fixture that
runs `alembic upgrade head` against a local Postgres. That migration currently
fails on `sqlmodel.sql.sqltypes.GUID` (unrelated, pre-existing). Rate-limit
tests don't need the DB at all — slowapi's behavior is verified at the HTTP
layer — so we sidestep the broken setup by living in this subdir.
"""

import os

import pytest

os.environ["TESTING"] = "1"


@pytest.fixture(scope="session", autouse=True)
def test_engine():
    """
    No-op override of the parent conftest's postgres+alembic setup.

    Rate-limit tests verify slowapi at the HTTP layer and don't need a DB.
    The parent fixture currently fails on a `sqlmodel.sql.sqltypes.GUID`
    migration issue unrelated to P1-4 — overriding it here keeps these tests
    runnable until that's fixed.
    """
    yield None
