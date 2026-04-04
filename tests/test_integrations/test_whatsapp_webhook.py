import hashlib
import hmac
import json

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.models.notification import NotificationAttempt
from backend.app.models.order import Order
from backend.app.models.store import Store


def _sign_body(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


@pytest.fixture
def wa_webhook_env(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_SECRET", "test-meta-app-secret")
    monkeypatch.setattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "verify-token-test")


def test_whatsapp_webhook_verify_success(client, wa_webhook_env):
    r = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify-token-test",
            "hub.challenge": "CHALLENGE_STRING",
        },
    )
    assert r.status_code == 200
    assert r.text == "CHALLENGE_STRING"


def test_whatsapp_webhook_verify_forbidden(client, wa_webhook_env):
    r = client.get(
        "/webhooks/whatsapp",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong",
            "hub.challenge": "x",
        },
    )
    assert r.status_code == 403


def test_whatsapp_webhook_post_rejects_bad_signature(client, wa_webhook_env):
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    r = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "Content-Type": "application/json",
        },
    )
    assert r.status_code == 403


def test_whatsapp_webhook_post_rejects_missing_signature(client, wa_webhook_env):
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    r = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 403


def test_whatsapp_webhook_post_accepts_valid_signature(client, wa_webhook_env):
    body = b'{"object":"whatsapp_business_account","entry":[]}'
    sig = _sign_body("test-meta-app-secret", body)
    r = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200
    assert r.json() == {"success": True}


def test_whatsapp_webhook_status_updates_attempt(client, wa_webhook_env, engine):
    Session = sessionmaker(bind=engine)
    db = Session()
    store = Store(name="S", external_store_id="tn_test_wh", status="active")
    db.add(store)
    db.flush()
    order = Order(store_id=store.id, external_id="O1", current_status="in_transit")
    db.add(order)
    db.flush()
    att = NotificationAttempt(
        store_id=store.id,
        order_id=order.id,
        event_type="in_transit",
        idempotency_key="unique-wa-webhook-test-1",
        template_name="shipping_in_transit_v1",
        status="sent",
        provider_message_id="wamid.webhook_test_1",
    )
    db.add(att)
    db.commit()
    db.close()

    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {
                                    "id": "wamid.webhook_test_1",
                                    "status": "delivered",
                                    "timestamp": "1609459200",
                                }
                            ]
                        }
                    }
                ]
            }
        ],
    }
    body = json.dumps(payload).encode("utf-8")
    sig = _sign_body("test-meta-app-secret", body)
    r = client.post(
        "/webhooks/whatsapp",
        content=body,
        headers={"X-Hub-Signature-256": sig, "Content-Type": "application/json"},
    )
    assert r.status_code == 200

    db2 = Session()
    row = (
        db2.query(NotificationAttempt).filter_by(provider_message_id="wamid.webhook_test_1").first()
    )
    assert row is not None
    assert row.provider_delivery_status == "delivered"
    assert row.provider_delivery_status_at is not None
    db2.close()
