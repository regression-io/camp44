from sqlmodel import Session, SQLModel, create_engine

from camp44.core.config import settings


def _engine_kwargs(url: str) -> dict:
    """
    Build ``create_engine`` kwargs for the given database URL.

    For PostgreSQL we configure an explicitly sized, self-healing pool:

    - ``pool_pre_ping`` discards dead connections before handing them out,
    - ``pool_recycle`` ages connections out periodically,
    - server-side ``idle_in_transaction_session_timeout`` makes Postgres kill a
      connection stranded mid-transaction.

    Together these fix stress-test finding **F3**: under load, sessions could be
    left checked out and ``idle in transaction``, permanently exhausting the
    bare default 5+10 pool until the container was restarted. Now a stranded
    connection is killed server-side and recycled, so the pool self-heals.

    SQLite (used by the test suite) has its own pool implementation and rejects
    ``pool_size``/``max_overflow``, so only ``echo`` is passed there.
    """
    kwargs: dict = {"echo": False}
    if url.startswith("postgresql"):
        opts = [
            f"idle_in_transaction_session_timeout={settings.DB_IDLE_IN_TX_TIMEOUT_MS}",
        ]
        if settings.DB_STATEMENT_TIMEOUT_MS > 0:
            opts.append(f"statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS}")
        kwargs.update(
            pool_size=settings.DB_POOL_SIZE,
            max_overflow=settings.DB_MAX_OVERFLOW,
            pool_timeout=settings.DB_POOL_TIMEOUT,
            pool_recycle=settings.DB_POOL_RECYCLE,
            pool_pre_ping=True,
            connect_args={
                "options": " ".join(f"-c {o}" for o in opts),
                "connect_timeout": settings.DB_CONNECT_TIMEOUT,
            },
        )
    return kwargs


# The database URL is taken from the settings object
engine = create_engine(settings.DATABASE_URL, **_engine_kwargs(settings.DATABASE_URL))


def get_session():
    """FastAPI dependency to get a DB session."""
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """Create database and tables if they don't exist."""
    # This is useful for initial setup or testing, but migrations with Alembic are preferred for production.
    SQLModel.metadata.create_all(engine)
