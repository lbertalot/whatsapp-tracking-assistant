import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreSettings


@pytest.fixture
def metrics_env(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]
    store = Store(name="Metrics Store", external_store_id=f"tn_m_{uid}", status="active")
    session.add(store)
    session.flush()

    settings = StoreSettings(store_id=store.id, onboarding_status="active")
    session.add(settings)

    now = datetime.utcnow()
    orders = [
        Order(
            store_id=store.id,
            external_id=f"m1_{uid}",
            normalized_phone="+595981111111",
            tracking_number="WRH-M1",
            current_status="delivered",
            notification_status="sent",
            first_notification_at=now - timedelta(hours=2),
            created_at=now - timedelta(hours=5),
        ),
        Order(
            store_id=store.id,
            external_id=f"m2_{uid}",
            normalized_phone="+595982222222",
            tracking_number="WRH-M2",
            current_status="in_transit",
            notification_status="sent",
            first_notification_at=now - timedelta(hours=1),
            created_at=now - timedelta(hours=3),
        ),
        Order(
            store_id=store.id,
            external_id=f"m3_{uid}",
            normalized_phone=None,
            invalid_phone=True,
            tracking_number="WRH-M3",
            current_status="pending_tracking",
        ),
        Order(
            store_id=store.id,
            external_id=f"m4_{uid}",
            normalized_phone="+595984444444",
            tracking_number="WRH-M4",
            current_status="in_transit",
            notification_status="failed",
            notification_error="WhatsApp API error",
        ),
    ]
    session.add_all(orders)
    session.commit()

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client

    app.dependency_overrides.clear()
    session.query(Order).filter(Order.store_id == store.id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()
    session.close()


def test_health_includes_worker_status(metrics_env):
    client = metrics_env
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data


def test_ready_checks_db(metrics_env):
    client = metrics_env
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["database"] == "connected"


def test_metrics_endpoint(metrics_env):
    client = metrics_env
    response = client.get("/metrics")
    assert response.status_code == 200
    data = response.json()
    assert "total_orders" in data
    assert "orders_notified" in data
    assert "pct_notified" in data
    assert "pct_invalid_phone" in data
    assert "pct_whatsapp_errors" in data


def test_metrics_calculates_pct_notified(metrics_env):
    client = metrics_env
    data = client.get("/metrics").json()
    assert data["orders_notified"] >= 1
    assert 0 <= data["pct_notified"] <= 100


def test_metrics_calculates_invalid_phone(metrics_env):
    client = metrics_env
    data = client.get("/metrics").json()
    assert data["pct_invalid_phone"] > 0
