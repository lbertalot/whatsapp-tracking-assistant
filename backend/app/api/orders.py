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
from backend.app.schemas.order import WebhookOrderPayload, WebhookOrderResponse
from backend.app.services.phone import normalize_phone

logger = logging.getLogger(__name__)

router = APIRouter()


def _verify_signature(body_bytes: bytes, signature: Optional[str]) -> bool:
    if not signature:
        return False
    expected = hmac.new(
        settings.WEBHOOK_SECRET_TOKEN.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhooks/orders", response_model=WebhookOrderResponse)
async def webhook_order(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    signature = request.headers.get("X-Webhook-Signature")

    if not _verify_signature(body_bytes, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    payload = WebhookOrderPayload(**json.loads(body_bytes))

    store = db.query(Store).filter(Store.external_store_id == payload.store_id).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    existing = (
        db.query(Order)
        .filter(Order.store_id == store.id, Order.external_id == payload.id)
        .first()
    )
    if existing:
        return WebhookOrderResponse(status="received", order_id=existing.id, invalid_phone=existing.invalid_phone)

    raw_phone = payload.customer.phone if payload.customer else None
    normalized = normalize_phone(raw_phone)
    is_invalid = raw_phone is not None and normalized is None

    order = Order(
        store_id=store.id,
        external_id=payload.id,
        customer_name=payload.customer.name if payload.customer else None,
        raw_phone=raw_phone,
        normalized_phone=normalized,
        invalid_phone=is_invalid,
        tracking_number=payload.shipping_tracking_number,
        tracking_url=payload.shipping_tracking_url,
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info("Order %s ingested for store %s (phone_valid=%s)", order.id, store.id, not is_invalid)

    return WebhookOrderResponse(
        status="received",
        order_id=order.id,
        invalid_phone=is_invalid if is_invalid else None,
    )
