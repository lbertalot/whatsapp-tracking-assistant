import hashlib
import hmac
import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.main import app


@pytest.fixture
def webhook_env(engine):
    from backend.app.models.order import Order
    from backend.app.models.store import Store, StoreInstallation

    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]
    store = Store(name="Webhook Store", external_store_id=f"tn_{uid}", status="active")
    session.add(store)
    session.flush()

    installation = StoreInstallation(
        store_id=store.id,
        order_source_type="tiendanube",
        is_active=True,
        access_token="fake-tn-token",
    )
    session.add(installation)
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


def _sign_body(body_bytes: bytes) -> str:
    return hmac.new(
        settings.WEBHOOK_SECRET_TOKEN.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()


def _order_payload(store_id: str, order_id: str = "12345", phone: str = "+595981123456"):
    return {
        "store_id": store_id,
        "id": order_id,
        "number": 100,
        "customer": {
            "phone": phone,
            "name": "Juan Pérez",
        },
        "shipping_tracking_number": "WRH-001",
        "shipping_tracking_url": "https://weraha.com/track/WRH-001",
    }


def _post_webhook(client, payload: dict, signature: str = None):
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["X-Webhook-Signature"] = signature
    return client.post("/webhooks/orders", content=body, headers=headers)


def test_webhook_creates_order(webhook_env):
    client, store = webhook_env
    payload = _order_payload(store.external_store_id)
    body = json.dumps(payload).encode()

    response = _post_webhook(client, payload, _sign_body(body))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"
    assert "order_id" in data


def test_webhook_idempotent(webhook_env):
    client, store = webhook_env
    payload = _order_payload(store.external_store_id, order_id="idem-1")
    body = json.dumps(payload).encode()
    sig = _sign_body(body)

    r1 = _post_webhook(client, payload, sig)
    assert r1.status_code == 200
    id1 = r1.json()["order_id"]

    r2 = _post_webhook(client, payload, sig)
    assert r2.status_code == 200
    assert r2.json()["order_id"] == id1


def test_webhook_normalizes_phone(webhook_env):
    client, store = webhook_env
    payload = _order_payload(store.external_store_id, order_id="phone-1", phone="0981123456")
    body = json.dumps(payload).encode()

    response = _post_webhook(client, payload, _sign_body(body))
    assert response.status_code == 200


def test_webhook_invalid_phone_marks_order(webhook_env):
    client, store = webhook_env
    payload = _order_payload(store.external_store_id, order_id="badphone", phone="123")
    body = json.dumps(payload).encode()

    response = _post_webhook(client, payload, _sign_body(body))
    assert response.status_code == 200
    data = response.json()
    assert data.get("invalid_phone") is True


def test_webhook_invalid_signature(webhook_env):
    client, store = webhook_env
    payload = _order_payload(store.external_store_id)

    response = _post_webhook(client, payload, "bad-signature")
    assert response.status_code == 401


def test_webhook_missing_signature(webhook_env):
    client, store = webhook_env
    payload = _order_payload(store.external_store_id)

    response = _post_webhook(client, payload)
    assert response.status_code == 401


def test_webhook_unknown_store(webhook_env):
    client, store = webhook_env
    payload = _order_payload("nonexistent_store_999")
    body = json.dumps(payload).encode()

    response = _post_webhook(client, payload, _sign_body(body))
    assert response.status_code == 404
