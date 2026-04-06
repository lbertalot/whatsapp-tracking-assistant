import uuid

from backend.app.core.security import create_access_token, hash_password
from backend.app.models.store import Store, StoreSettings
from backend.app.models.user import StoreUser
from tests.conftest import TestingSession


def _setup_env(db):
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"Settings Store {uid}", external_store_id=f"set-{uid}", status="active")
    db.add(store)
    db.flush()

    settings = StoreSettings(
        store_id=store.id,
        onboarding_status="active",
        template_in_transit="shipping_in_transit_v1",
        template_delivered="shipping_delivered_v1",
        ecommerce_sync_enabled=True,
        whatsapp_enabled=True,
        whatsapp_phone_number_id="1234567890",
    )
    db.add(settings)

    user = StoreUser(
        store_id=store.id,
        email=f"set-{uid}@test.com",
        password_hash=hash_password("pw"),
    )
    db.add(user)
    db.flush()
    db.commit()

    token = create_access_token(user_id=user.id, store_id=store.id)
    return store, user, token


def test_get_settings_requires_auth(client):
    resp = client.get("/api/settings")
    assert resp.status_code == 401


def test_get_settings(client):
    db = TestingSession()
    try:
        _, _, token = _setup_env(db)

        resp = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_in_transit"] == "shipping_in_transit_v1"
        assert data["template_delivered"] == "shipping_delivered_v1"
        assert data["ecommerce_sync_enabled"] is True
        assert data["whatsapp_enabled"] is True
        assert data["onboarding_status"] == "active"
        assert data["whatsapp_token_configured"] is False
        assert data["whatsapp_template_language"] == "es"
        assert data["whatsapp_include_body_params"] is True
        assert data["whatsapp_include_customer_name_in_body"] is False
    finally:
        db.rollback()
        db.close()


def test_update_settings_templates(client):
    db = TestingSession()
    try:
        _, _, token = _setup_env(db)

        resp = client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "template_in_transit": "custom_transit_v2",
                "template_delivered": "custom_delivered_v2",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["template_in_transit"] == "custom_transit_v2"
        assert data["template_delivered"] == "custom_delivered_v2"
    finally:
        db.rollback()
        db.close()


def test_update_settings_isolation(client):
    db = TestingSession()
    try:
        store_a, _, token_a = _setup_env(db)

        uid_b = uuid.uuid4().hex[:8]
        store_b = Store(name=f"Other {uid_b}", external_store_id=f"oth-{uid_b}", status="active")
        db.add(store_b)
        db.flush()
        settings_b = StoreSettings(store_id=store_b.id, template_in_transit="original_b")
        db.add(settings_b)
        db.commit()

        client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token_a}"},
            json={"template_in_transit": "changed_by_a"},
        )

        db.refresh(settings_b)
        assert settings_b.template_in_transit == "original_b"
    finally:
        db.rollback()
        db.close()


def test_put_settings_requires_auth(client):
    resp = client.put("/api/settings", json={"template_in_transit": "x"})
    assert resp.status_code == 401


def test_put_ecommerce_sync_and_phone_region(client):
    db = TestingSession()
    try:
        _, _, token = _setup_env(db)
        resp = client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"ecommerce_sync_enabled": False, "default_phone_region": "AR"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["ecommerce_sync_enabled"] is False
        assert data["default_phone_region"] == "AR"
        resp2 = client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"ecommerce_sync_enabled": True, "default_phone_region": None},
        )
        assert resp2.status_code == 200
        assert resp2.json()["ecommerce_sync_enabled"] is True
        assert resp2.json().get("default_phone_region") in (None, "")
    finally:
        db.rollback()
        db.close()


def test_put_whatsapp_include_body_params(client):
    db = TestingSession()
    try:
        _, _, token = _setup_env(db)
        resp = client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={"whatsapp_include_body_params": False},
        )
        assert resp.status_code == 200
        assert resp.json()["whatsapp_include_body_params"] is False
        get_r = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
        assert get_r.json()["whatsapp_include_body_params"] is False
    finally:
        db.rollback()
        db.close()


def test_put_whatsapp_token_not_exposed_in_get(client):
    db = TestingSession()
    try:
        _, _, token = _setup_env(db)
        put = client.put(
            "/api/settings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "whatsapp_access_token": "EAA_SECRET_META_NOT_IN_RESPONSE",
                "whatsapp_template_language": "es",
            },
        )
        assert put.status_code == 200
        assert "EAA_SECRET" not in put.text
        assert put.json()["whatsapp_token_configured"] is True

        resp = client.get("/api/settings", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["whatsapp_token_configured"] is True
        assert "EAA_SECRET" not in resp.text
        assert "whatsapp_access_token" not in data
    finally:
        db.rollback()
        db.close()
