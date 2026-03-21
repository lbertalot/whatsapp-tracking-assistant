import uuid

from tests.conftest import TestingSession
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.store import Store, StoreSettings
from backend.app.models.user import StoreUser


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
        weraha_enabled=True,
        whatsapp_enabled=True,
        whatsapp_phone_number_id="1234567890",
    )
    db.add(settings)

    user = StoreUser(store_id=store.id, email=f"set-{uid}@test.com", password_hash=hash_password("pw"))
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
        assert data["weraha_enabled"] is True
        assert data["whatsapp_enabled"] is True
        assert data["onboarding_status"] == "active"
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
            json={"template_in_transit": "custom_transit_v2", "template_delivered": "custom_delivered_v2"},
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
