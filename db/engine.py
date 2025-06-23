"""Central SQLAlchemy engine/session factory with tenant RLS support.

This module **does not** replace the existing `camp44.db.session` yet. It is
introduced as part of the secure-storage overhaul. Once auth middleware is
wired, the rest of the codebase will migrate to use the helpers defined here.

Key features
------------
* Forces TLS (`sslmode=require`) when connecting to Postgres.
* Uses credentials fetched from `AWS Secrets Manager` (fallback to env vars for
  local/dev) via `db.secrets.get_secret`.
* On each connection checkout, sets the session variable `app.tenant_id` so
  Postgres RLS policies can enforce data isolation.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import event, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from db.secrets import get_secret

# ---------------------------------------------------------------------------
# Connection URL helpers
# ---------------------------------------------------------------------------

_DEFAULT_DB_URL = os.getenv(
    "DATABASE_URL", "sqlite+aiosqlite:///./test.db"  # local fallback
)


def _build_db_url() -> str:
    if _DEFAULT_DB_URL.startswith("postgresql"):
        # Running with env-provided URL (e.g. docker-compose local)
        return f"{_DEFAULT_DB_URL}?sslmode=require"

    if _DEFAULT_DB_URL.startswith("sqlite"):
        # Tests / local dev keep sqlite
        return _DEFAULT_DB_URL

    # Attempt to build from AWS Secrets Manager
    try:
        creds: dict[str, str] = get_secret("camp44/rds", parse_json=True)
    except Exception:
        return _DEFAULT_DB_URL  # fall back

    url = URL.create(
        drivername="postgresql+asyncpg",
        username=creds["username"],
        password=creds["password"],
        host=creds["host"],
        port=int(creds.get("port", 5432)),
        database=creds["dbname"],
    )
    return str(url) + "?sslmode=require"


DATABASE_URL_ASYNC: str = _build_db_url()


# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------
async_engine: AsyncEngine = create_async_engine(
    DATABASE_URL_ASYNC,
    pool_pre_ping=True,
    pool_recycle=1800,
)

# Set tenant_id for each new connection --------------------------------------

@event.listens_for(async_engine.sync_engine, "connect", once=False)
def _set_tenant_on_connect(dbapi_con, con_record):  # type: ignore[unused-argument]
    # The actual tenant id is injected later via execution options.
    dbapi_con.execute("SET app.tenant_id TO NULL")


async_session_maker = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# Public dependency helpers
# ---------------------------------------------------------------------------

@asynccontextmanager
async def get_async_db(tenant_id: Optional[str] = None) -> AsyncGenerator[AsyncSession, None]:
    """Yield an `AsyncSession` with the given tenant set for RLS.

    The surrounding auth middleware should provide `tenant_id`.
    """
    async with async_session_maker() as session:  # type: AsyncSession
        if tenant_id is not None:
            await session.execute(text("SET app.tenant_id = :tid"), {"tid": tenant_id})
        yield session
