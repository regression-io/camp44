import os
import pytest
from typing import Generator

from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from camp44.api import deps
from camp44.core.security import get_password_hash
from camp44.main import app
from camp44.models import User

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Create the tables once for the entire test session
    SQLModel.metadata.create_all(bind=engine)
    yield
    # Drop the tables and remove the DB file at the end
    SQLModel.metadata.drop_all(bind=engine)
    os.remove("test.db")


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a new database session for each test, wrapped in a transaction."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """Get a TestClient instance that uses the test-specific session."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[deps.get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    del app.dependency_overrides[deps.get_db]


@pytest.fixture(scope="function")
def test_user(db_session: Session) -> User:
    user_data = {"email": "test@example.com", "password": "testpassword"}
    hashed_password = get_password_hash(user_data["password"])
    db_user = User(email=user_data["email"], hashed_password=hashed_password, is_active=True)
    db_session.add(db_user)
    db_session.commit()
    db_session.refresh(db_user)
    return db_user
