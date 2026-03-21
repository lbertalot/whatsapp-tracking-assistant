import hmac
import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.order import Order
from backend.app.models.store import Store
from backend.app.services.phone import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter()

LGPD_EVENTS = {"store/redact", "customers/redact", "customers/data_request"}
ORDER_EVENTS = {"order/created", "order/paid", "order/fulfilled"}


def _verify_tn_hmac(body_bytes: bytes, signature: Optional[str]) -> bool:
    if not signature:
        return False
    expected = hmac.new(
        settings.TIENDANUBE_CLIENT_SECRET.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/tiendanube")
async def tiendanube_webhook(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    signature = request.headers.get("X-Linkedstore-Hmac-Sha256")

    if not _verify_tn_hmac(body_bytes, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")

    payload = json.loads(body_bytes)
    event = payload.get("event", "")

    if event in LGPD_EVENTS:
        logger.info("LGPD event received: %s for store %s", event, payload.get("store_id"))
        return {"status": "acknowledged", "event": event}

    if event not in ORDER_EVENTS:
        return {"status": "ignored", "event": event}

    store_id_ext = str(payload.get("store_id", ""))
    store = db.query(Store).filter(Store.external_store_id == store_id_ext).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    order_ext_id = str(payload.get("id", ""))

    existing = (
        db.query(Order)
        .filter(Order.store_id == store.id, Order.external_id == order_ext_id)
        .first()
    )

    if event == "order/fulfilled" and existing:
        tracking = payload.get("shipping_tracking_number")
        tracking_url = payload.get("shipping_tracking_url")
        if tracking:
            existing.tracking_number = tracking
            existing.tracking_url = tracking_url
            if existing.current_status in (None, "pending_tracking"):
                existing.current_status = "ready_for_polling"
            db.commit()
            logger.info("Order %s tracking updated: %s", existing.id, tracking)
            return {"status": "received", "order_id": existing.id, "tracking_updated": True}
        return {"status": "received", "order_id": existing.id, "tracking_updated": False}

    if existing:
        return {"status": "received", "order_id": existing.id}

    customer = payload.get("customer") or {}
    raw_phone = customer.get("phone")
    normalized = normalize_phone(raw_phone)
    is_invalid = raw_phone is not None and normalized is None

    order = Order(
        store_id=store.id,
        external_id=order_ext_id,
        customer_name=customer.get("name"),
        raw_phone=raw_phone,
        normalized_phone=normalized,
        invalid_phone=is_invalid,
        tracking_number=payload.get("shipping_tracking_number"),
        tracking_url=payload.get("shipping_tracking_url"),
        current_status="pending_tracking",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info("TN order %s ingested for store %s", order.id, store.id)
    return {"status": "received", "order_id": order.id}
