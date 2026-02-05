from sqlmodel import create_engine, Session, SQLModel

from camp44.core.config import settings

# The database URL is taken from the settings object
engine = create_engine(settings.DATABASE_URL, echo=False)


def get_session():
    """FastAPI dependency to get a DB session."""
    with Session(engine) as session:
        yield session


def create_db_and_tables():
    """Create database and tables if they don't exist."""
    # This is useful for initial setup or testing, but migrations with Alembic are preferred for production.
    SQLModel.metadata.create_all(engine)
