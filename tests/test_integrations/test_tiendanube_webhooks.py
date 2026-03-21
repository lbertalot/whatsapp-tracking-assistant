import uuid
import hmac
import hashlib
import json

import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.store import Store, StoreInstallation
from backend.app.models.order import Order


@pytest.fixture
def tn_webhook_env(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]
    store = Store(name="TN Webhook Store", external_store_id=f"tn_w_{uid}", status="active")
    session.add(store)
    session.flush()

    inst = StoreInstallation(
        store_id=store.id,
        order_source_type="tiendanube",
        access_token="fake-token",
        is_active=True,
    )
    session.add(inst)
    session.commit()

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client, store

    app.dependency_overrides.clear()
    session.query(Order).filter(Order.store_id == store.id).delete()
    session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).delete()
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()
    session.close()


def _sign_tn(body_bytes: bytes) -> str:
    return hmac.new(
        settings.TIENDANUBE_CLIENT_SECRET.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()


def _tn_order_payload(store_id: str, order_id: int = 1001):
    return {
        "event": "order/created",
        "store_id": store_id,
        "id": order_id,
        "number": order_id,
        "customer": {
            "phone": "+595981555666",
            "name": "Cliente Test",
        },
        "shipping_tracking_number": None,
        "shipping_tracking_url": None,
    }


def _post_tn_webhook(client, payload, signature=None):
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if signature:
        headers["X-Linkedstore-Hmac-Sha256"] = signature
    return client.post("/webhooks/tiendanube", content=body, headers=headers)


def test_webhook_hmac_valid(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_order_payload(store.external_store_id)
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200


def test_webhook_hmac_invalid(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_order_payload(store.external_store_id)

    response = _post_tn_webhook(client, payload, "invalid-hmac")
    assert response.status_code == 401


def test_webhook_order_created(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_order_payload(store.external_store_id, order_id=2001)
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


def test_webhook_order_fulfilled_updates_tracking(tn_webhook_env):
    client, store = tn_webhook_env

    create_payload = _tn_order_payload(store.external_store_id, order_id=3001)
    body = json.dumps(create_payload).encode()
    _post_tn_webhook(client, create_payload, _sign_tn(body))

    fulfill_payload = {
        "event": "order/fulfilled",
        "store_id": store.external_store_id,
        "id": 3001,
        "number": 3001,
        "customer": {"phone": "+595981555666", "name": "Cliente Test"},
        "shipping_tracking_number": "WRH-FULFILL-001",
        "shipping_tracking_url": "https://weraha.com/track/WRH-FULFILL-001",
    }
    body2 = json.dumps(fulfill_payload).encode()
    response = _post_tn_webhook(client, fulfill_payload, _sign_tn(body2))
    assert response.status_code == 200
    data = response.json()
    assert data.get("tracking_updated") is True


def test_webhook_idempotent(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_order_payload(store.external_store_id, order_id=4001)
    body = json.dumps(payload).encode()
    sig = _sign_tn(body)

    r1 = _post_tn_webhook(client, payload, sig)
    r2 = _post_tn_webhook(client, payload, sig)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["order_id"] == r2.json()["order_id"]


def test_webhook_store_redact(tn_webhook_env):
    client, store = tn_webhook_env
    payload = {"event": "store/redact", "store_id": store.external_store_id}
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200


def test_webhook_customers_redact(tn_webhook_env):
    client, store = tn_webhook_env
    payload = {"event": "customers/redact", "store_id": store.external_store_id, "customer": {"id": 123}}
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200


def test_webhook_customers_data_request(tn_webhook_env):
    client, store = tn_webhook_env
    payload = {"event": "customers/data_request", "store_id": store.external_store_id, "customer": {"id": 456}}
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200
