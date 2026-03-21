import uuid

import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.db.session import get_db
from backend.app.main import app


@pytest.fixture
def auth_env(engine):
    """Provides a client + store + user sharing the same in-memory DB."""
    from backend.app.models.store import Store
    from backend.app.models.user import StoreUser
    from backend.app.core.security import hash_password

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
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()
    session.close()


def test_hash_and_verify_password():
    from backend.app.core.security import hash_password, verify_password

    hashed = hash_password("mypassword")
    assert hashed != "mypassword"
    assert verify_password("mypassword", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_create_and_decode_jwt():
    from backend.app.core.security import create_access_token, decode_access_token

    token = create_access_token(user_id=1, store_id=10)
    payload = decode_access_token(token)
    assert payload["user_id"] == 1
    assert payload["store_id"] == 10


def test_login_success(auth_env):
    client, store, user, email = auth_env
    response = client.post("/auth/login", json={"email": email, "password": "Secret123!"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password(auth_env):
    client, store, user, email = auth_env
    response = client.post("/auth/login", json={"email": email, "password": "wrong"})
    assert response.status_code == 401


def test_login_nonexistent_user(client):
    response = client.post("/auth/login", json={"email": "nobody@test.com", "password": "x"})
    assert response.status_code == 401


def test_me_authenticated(auth_env):
    client, store, user, email = auth_env
    login = client.post("/auth/login", json={"email": email, "password": "Secret123!"})
    token = login.json()["access_token"]
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == email
    assert data["store_id"] == store.id


def test_me_unauthenticated(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_me_invalid_token(client):
    response = client.get("/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401
