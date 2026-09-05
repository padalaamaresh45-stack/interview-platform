import pytest
import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.database import Base, get_db
from app.main import app

_BASE_URL, _, _ = settings.database_url.rpartition("/")
_TEST_DB_NAME = "interview_platform_test"
TEST_DATABASE_URL = f"{_BASE_URL}/{_TEST_DB_NAME}"


def _ensure_test_database_exists() -> None:
    admin_engine = create_engine(f"{_BASE_URL}/postgres", isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            sqlalchemy.text("SELECT 1 FROM pg_database WHERE datname = :name"),
            {"name": _TEST_DB_NAME},
        ).first()
        if exists is None:
            conn.execute(sqlalchemy.text(f'CREATE DATABASE "{_TEST_DB_NAME}"'))
    admin_engine.dispose()


_ensure_test_database_exists()

engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _reset_schema():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    def override_get_db():
        session = TestSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
