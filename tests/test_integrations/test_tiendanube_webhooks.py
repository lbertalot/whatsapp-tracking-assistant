import hashlib
import hmac
import json
import time
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation


@pytest.fixture
def tn_webhook_env(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    # TN user_id es numérico; el webhook manda store_id como número.
    tn_user_id = 9_000_000 + (int(uuid.uuid4().hex[:6], 16) % 100_000)
    store = Store(name="TN Webhook Store", external_store_id=str(tn_user_id), status="active")
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


def _tn_minimal_payload(store_id: str, event: str, order_id: int):
    """Contrato real TN: solo store_id, event, id (numérico en origen)."""
    return {
        "event": event,
        "store_id": int(store_id) if store_id.isdigit() else store_id,
        "id": order_id,
    }


def _post_tn_webhook(client, payload, signature=None):
    body = json.dumps(payload)
    headers = {"Content-Type": "application/json"}
    if signature:
        headers["X-Linkedstore-Hmac-Sha256"] = signature
    return client.post("/webhooks/tiendanube", content=body, headers=headers)


def _order_detail_created(order_id: int):
    return {
        "id": order_id,
        "contact_phone": "+595981555666",
        "contact_name": "Cliente Test",
        "customer": {"name": "Cliente Test", "phone": "+595981555666"},
    }


def _order_detail_fulfilled(order_id: int):
    return {
        "id": order_id,
        "contact_phone": "+595981555666",
        "contact_name": "Cliente Test",
        "fulfillment_orders": [
            {
                "tracking_info": {
                    "code": "WRH-FULFILL-001",
                    "url": "https://weraha.com/track/WRH-FULFILL-001",
                }
            }
        ],
    }


def test_webhook_hmac_valid(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_minimal_payload(store.external_store_id, "order/created", 1001)
    body = json.dumps(payload).encode()

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        return_value=_order_detail_created(1001),
    ):
        response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200


def test_webhook_hmac_invalid(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_minimal_payload(store.external_store_id, "order/created", 1001)

    response = _post_tn_webhook(client, payload, "invalid-hmac")
    assert response.status_code == 401


def test_webhook_order_created(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_minimal_payload(store.external_store_id, "order/created", 2001)
    body = json.dumps(payload).encode()

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        return_value=_order_detail_created(2001),
    ):
        response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "received"


def test_webhook_order_fulfilled_updates_tracking(tn_webhook_env):
    client, store = tn_webhook_env

    create_payload = _tn_minimal_payload(store.external_store_id, "order/created", 3001)
    body = json.dumps(create_payload).encode()

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        return_value=_order_detail_created(3001),
    ):
        _post_tn_webhook(client, create_payload, _sign_tn(body))

    fulfill_payload = _tn_minimal_payload(store.external_store_id, "order/fulfilled", 3001)
    body2 = json.dumps(fulfill_payload).encode()

    def _fetch_side_effect(user_id, order_id, access_token, aggregates=None, timeout=2.5):
        if aggregates == "fulfillment_orders":
            return _order_detail_fulfilled(order_id)
        return _order_detail_created(order_id)

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        side_effect=_fetch_side_effect,
    ):
        response = _post_tn_webhook(client, fulfill_payload, _sign_tn(body2))
    assert response.status_code == 200
    data = response.json()
    assert data.get("tracking_updated") is True


def test_webhook_idempotent(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_minimal_payload(store.external_store_id, "order/created", 4001)
    body = json.dumps(payload).encode()
    sig = _sign_tn(body)

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        return_value=_order_detail_created(4001),
    ):
        r1 = _post_tn_webhook(client, payload, sig)
        r2 = _post_tn_webhook(client, payload, sig)
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["order_id"] == r2.json()["order_id"]


def test_webhook_store_redact(tn_webhook_env, engine):
    client, store = tn_webhook_env
    payload = {"event": "store/redact", "store_id": store.external_store_id}
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200

    S2 = sessionmaker(bind=engine)
    s2 = S2()
    try:
        st = s2.query(Store).filter(Store.id == store.id).first()
        assert st is not None
        assert st.status == "redacted"
        inst = s2.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).first()
        assert inst.is_active is False
    finally:
        s2.close()


def test_webhook_customers_redact(tn_webhook_env):
    client, store = tn_webhook_env
    payload = {
        "event": "customers/redact",
        "store_id": store.external_store_id,
        "customer": {"id": 123},
    }
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200


def test_webhook_customers_data_request(tn_webhook_env):
    client, store = tn_webhook_env
    payload = {
        "event": "customers/data_request",
        "store_id": store.external_store_id,
        "customer": {"id": 456},
    }
    body = json.dumps(payload).encode()

    response = _post_tn_webhook(client, payload, _sign_tn(body))
    assert response.status_code == 200


def test_webhook_responds_fast(tn_webhook_env):
    client, store = tn_webhook_env
    payload = _tn_minimal_payload(store.external_store_id, "order/created", 5001)
    body = json.dumps(payload).encode()

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        return_value=_order_detail_created(5001),
    ):
        t0 = time.perf_counter()
        response = _post_tn_webhook(client, payload, _sign_tn(body))
        elapsed = time.perf_counter() - t0

    assert response.status_code == 200
    assert elapsed < 3.0


def test_webhook_tracking_info_from_payload_without_api_aggregate(tn_webhook_env):
    """Si el POST incluye tracking (p.ej. tests o extensión), no exige fulfillment_orders."""
    client, store = tn_webhook_env

    create_payload = _tn_minimal_payload(store.external_store_id, "order/created", 6001)
    body = json.dumps(create_payload).encode()
    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        return_value=_order_detail_created(6001),
    ):
        _post_tn_webhook(client, create_payload, _sign_tn(body))

    fulfill_payload = {
        "event": "order/fulfilled",
        "store_id": int(store.external_store_id),
        "id": 6001,
        "tracking_info": {"code": "TRACK-PAYLOAD-1", "url": "https://example.com/t"},
    }
    body2 = json.dumps(fulfill_payload).encode()

    with patch(
        "backend.app.api.webhooks_tn.tn_service.fetch_order",
        side_effect=AssertionError("should not need API when tracking_info in payload"),
    ):
        response = _post_tn_webhook(client, fulfill_payload, _sign_tn(body2))

    assert response.status_code == 200
    assert response.json().get("tracking_updated") is True
