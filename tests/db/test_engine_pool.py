"""
Engine/pool configuration tests (stress-test finding F3).

Verifies the PostgreSQL pool is explicitly sized + self-healing, that the
idle-in-transaction timeout (the actual leak fix) is applied, and that the
sqlite test path still builds without pool args.
"""

from camp44.core.config import settings
from camp44.db import session as db_session


def test_postgres_pool_is_sized_and_self_healing():
    """Postgres engine gets pre-ping, sizing, and the idle-in-tx self-heal."""
    kw = db_session._engine_kwargs("postgresql://u:p@h:5432/db")
    assert kw["pool_pre_ping"] is True
    assert kw["pool_size"] == settings.DB_POOL_SIZE
    assert kw["max_overflow"] == settings.DB_MAX_OVERFLOW
    assert kw["pool_timeout"] == settings.DB_POOL_TIMEOUT
    assert kw["pool_recycle"] == settings.DB_POOL_RECYCLE
    opts = kw["connect_args"]["options"]
    assert (
        f"idle_in_transaction_session_timeout={settings.DB_IDLE_IN_TX_TIMEOUT_MS}"
        in opts
    )
    assert kw["connect_args"]["connect_timeout"] == settings.DB_CONNECT_TIMEOUT


def test_statement_timeout_off_by_default_on_when_set(monkeypatch):
    """statement_timeout is omitted at 0 and included when configured."""
    kw = db_session._engine_kwargs("postgresql://u:p@h:5432/db")
    assert "statement_timeout" not in kw["connect_args"]["options"]

    monkeypatch.setattr(settings, "DB_STATEMENT_TIMEOUT_MS", 45000)
    kw2 = db_session._engine_kwargs("postgresql://u:p@h:5432/db")
    assert "statement_timeout=45000" in kw2["connect_args"]["options"]


def test_sqlite_gets_no_pool_args():
    """SQLite path passes only echo — pool sizing args would error there."""
    kw = db_session._engine_kwargs("sqlite:///./test.db")
    assert kw == {"echo": False}
    assert "pool_size" not in kw
    assert "connect_args" not in kw


def test_module_engine_built():
    """The module-level engine constructs without raising."""
    assert db_session.engine is not None
    assert db_session.engine.url.drivername.startswith(("postgresql", "sqlite"))
