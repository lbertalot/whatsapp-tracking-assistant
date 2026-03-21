import uuid
from datetime import datetime

from tests.conftest import TestingSession
from backend.app.core.security import create_access_token, hash_password
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreSettings
from backend.app.models.user import StoreUser


def _setup_env(db):
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"Stats Store {uid}", external_store_id=f"stats-{uid}", status="active")
    db.add(store)
    db.flush()

    settings = StoreSettings(store_id=store.id, onboarding_status="active")
    db.add(settings)

    user = StoreUser(store_id=store.id, email=f"stats-{uid}@test.com", password_hash=hash_password("pw"))
    db.add(user)
    db.flush()

    db.add_all([
        Order(store_id=store.id, external_id="O1", current_status="in_transit", notification_status="sent",
              first_notification_at=datetime(2026, 1, 1), normalized_phone="+595981000001"),
        Order(store_id=store.id, external_id="O2", current_status="in_transit", notification_status="failed",
              normalized_phone="+595981000002"),
        Order(store_id=store.id, external_id="O3", current_status="in_transit", invalid_phone=True),
        Order(store_id=store.id, external_id="O4", current_status="pending_tracking",
              normalized_phone="+595981000004"),
    ])
    db.commit()

    token = create_access_token(user_id=user.id, store_id=store.id)
    return store, user, token


def test_panel_stats_requires_auth(client):
    resp = client.get("/panel/stats")
    assert resp.status_code == 401


def test_panel_stats_scoped_by_store(client):
    db = TestingSession()
    try:
        store, user, token = _setup_env(db)

        uid2 = uuid.uuid4().hex[:8]
        store2 = Store(name=f"Other {uid2}", external_store_id=f"other-{uid2}", status="active")
        db.add(store2)
        db.flush()
        db.add(Order(store_id=store2.id, external_id="X1", current_status="delivered",
                     notification_status="sent", first_notification_at=datetime(2026, 1, 1)))
        db.commit()

        resp = client.get("/panel/stats", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_orders"] == 4
        assert data["orders_notified"] == 1
        assert data["orders_errors"] == 1
        assert data["orders_invalid_phone"] == 1
    finally:
        db.rollback()
        db.close()


def test_panel_stats_response_schema(client):
    db = TestingSession()
    try:
        _, _, token = _setup_env(db)

        resp = client.get("/panel/stats", headers={"Authorization": f"Bearer {token}"})
        data = resp.json()

        for key in ["total_orders", "orders_notified", "pct_notified",
                     "orders_errors", "pct_errors", "orders_invalid_phone", "pct_invalid_phone"]:
            assert key in data, f"Missing key: {key}"

        assert data["pct_notified"] == 25.0
        assert data["pct_errors"] == 25.0
        assert data["pct_invalid_phone"] == 25.0
    finally:
        db.rollback()
        db.close()
