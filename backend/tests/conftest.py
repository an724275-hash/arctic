import os

os.environ["ENVIRONMENT"] = "test"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from alembic import command
from alembic.config import Config

from app.config import settings
from app.db import get_db
from app.seed import seed_demo
from app.security import create_access_token


@pytest.fixture(scope="session")
def test_engine():
    url = make_url(os.getenv("TEST_DATABASE_URL", settings.database_url)).set(database="arctic_test")
    engine = create_engine(url, pool_pre_ping=True, connect_args={"options": "-c timezone=UTC"})
    with engine.begin() as connection:
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db(test_engine):
    with test_engine.connect() as connection:
        transaction = connection.begin()
        session = Session(bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
        try:
            yield session
        finally:
            session.close()
            transaction.rollback()


@pytest.fixture
def users(db):
    result = seed_demo(db, "DemoPass123!")
    db.commit()
    return result


@pytest.fixture
def client(db, users, tmp_path, monkeypatch):
    from app.main import app

    monkeypatch.setattr(settings, "uploads_dir", tmp_path / "uploads")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(users):
    def headers(role):
        user = users[role] if isinstance(role, str) else role
        return {"Authorization": f"Bearer {create_access_token(user)}"}

    return headers
