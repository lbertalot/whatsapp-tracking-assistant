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


def test_tn_oauth_state_roundtrip():
    from backend.app.core.security import create_tn_oauth_state, decode_tn_oauth_state

    state = create_tn_oauth_state(store_id=42)
    data = decode_tn_oauth_state(state)
    assert data is not None
    assert data["store_id"] == 42
    assert data["purpose"] == "tn_oauth"


def test_tn_oauth_state_rejects_wrong_purpose():
    from datetime import datetime, timedelta

    from jose import jwt

    from backend.app.core.config import settings
    from backend.app.core.security import decode_tn_oauth_state

    bad = jwt.encode(
        {"store_id": 1, "purpose": "other", "exp": datetime.utcnow() + timedelta(minutes=5)},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    assert decode_tn_oauth_state(bad) is None


def test_login_email_case_insensitive(auth_env):
    client, store, user, email = auth_env
    response = client.post("/auth/login", json={"email": email.upper(), "password": "Secret123!"})
    assert response.status_code == 200
    assert "access_token" in response.json()


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
    assert data["tiendanube_user_id"] == store.external_store_id
    assert data["needs_tiendanube"] is True


def test_me_unauthenticated(client):
    response = client.get("/me")
    assert response.status_code == 401


def test_me_invalid_token(client):
    response = client.get("/me", headers={"Authorization": "Bearer invalid.token.here"})
    assert response.status_code == 401


def test_register_success_snake_case(client):
    response = client.post(
        "/auth/register",
        json={
            "email": "newmerchant@example.com",
            "password": "Secret123!",
            "store_name": "Mi Tienda Nueva",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    from backend.app.core.security import decode_access_token

    payload = decode_access_token(data["access_token"])
    assert payload["user_id"] is not None
    assert payload["store_id"] is not None

    me = client.get("/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "newmerchant@example.com"
    assert body["store_name"] == "Mi Tienda Nueva"
    assert body["role"] == "owner"
    assert body["tiendanube_user_id"] is None
    assert body["needs_tiendanube"] is True


def test_register_success_camel_case_store_name(client):
    """Compat: algunos frontends envían storeName en lugar de store_name."""
    response = client.post(
        "/auth/register",
        json={
            "email": "camelcase@example.com",
            "password": "Secret123!",
            "storeName": "Berta Shop",
        },
    )
    assert response.status_code == 201
    assert "access_token" in response.json()


def test_register_duplicate_email(client):
    body = {
        "email": "dup_merchant@test.com",
        "password": "Secret123!",
        "store_name": "Tienda Dup",
    }
    assert client.post("/auth/register", json=body).status_code == 201
    r2 = client.post("/auth/register", json=body)
    assert r2.status_code == 409
    assert "registrado" in str(r2.json().get("detail", "")).lower()


def test_register_password_too_short(client):
    response = client.post(
        "/auth/register",
        json={"email": "shortpw@test.com", "password": "short", "store_name": "AB"},
    )
    assert response.status_code == 422


def test_register_store_name_too_short(client):
    response = client.post(
        "/auth/register",
        json={"email": "badname@test.com", "password": "Secret123!", "store_name": "x"},
    )
    assert response.status_code == 422
