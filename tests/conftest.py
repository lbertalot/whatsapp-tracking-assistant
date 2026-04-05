import os
import uuid

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ.setdefault("APP_ENV", "testing")
os.environ.setdefault("TIENDANUBE_APP_ID", "test-tn-app-id")
os.environ.setdefault("TIENDANUBE_CLIENT_SECRET", "test-tn-client-secret")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.app.models  # noqa: F401
from backend.app.db.base import Base

TEST_ENGINE = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(TEST_ENGINE, "connect")
def _enable_sqlite_fk(dbapi_conn, connection_record):
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


Base.metadata.create_all(bind=TEST_ENGINE)

TestingSession = sessionmaker(bind=TEST_ENGINE)

# Background tasks and any code using SessionLocal() must share TEST_ENGINE (one in-memory DB).
import backend.app.db.session as _db_session

_db_session.SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=TEST_ENGINE,
)

from backend.app.db.session import get_db
from backend.app.main import app


@pytest.fixture(scope="session")
def engine():
    return TEST_ENGINE


@pytest.fixture
def db_session():
    session = TestingSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def client():
    def _override():
        session = TestingSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_env(engine):
    """Client + store + user compartiendo la misma DB de test (in-memory)."""
    from backend.app.core.security import hash_password
    from backend.app.models.store import Store, StoreInstallation, StoreSettings
    from backend.app.models.user import StoreUser

    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]
    store = Store(name="Auth Store", external_store_id=f"tn_{uid}")
    session.add(store)
    session.flush()

    email = f"merchant_{uid}@test.com"
    user = StoreUser(
        store_id=store.id,
        email=email,
        password_hash=hash_password("Secret123!"),
    )
    session.add(user)
    session.commit()

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client, store, user, email

    app.dependency_overrides.clear()
    session.query(StoreUser).filter(StoreUser.id == user.id).delete()
    session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()
    session.close()
