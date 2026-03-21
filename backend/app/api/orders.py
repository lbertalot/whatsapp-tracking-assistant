import hmac
import hashlib
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.order import Order
from backend.app.models.store import Store
from backend.app.models.user import StoreUser
from backend.app.schemas.order import (
    OrderListItem,
    OrderListResponse,
    WebhookOrderPayload,
    WebhookOrderResponse,
)
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


@router.get("/orders", response_model=OrderListResponse)
def list_orders(
    status_filter: Optional[str] = Query(None, alias="status"),
    notification_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: StoreUser = Depends(get_current_user),
):
    query = db.query(Order).filter(Order.store_id == current_user.store_id)

    if status_filter:
        query = query.filter(Order.current_status == status_filter)
    if notification_status:
        query = query.filter(Order.notification_status == notification_status)

    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    return OrderListResponse(
        items=[
            OrderListItem(
                order_id=o.id,
                store_id=o.store_id,
                status=o.current_status,
                notification_status=o.notification_status,
                last_message_type=o.last_message_type,
                last_template_name=o.last_template_name,
                last_message_preview=o.last_message_preview,
                last_notification_at=str(o.last_notification_at) if o.last_notification_at else None,
                error=o.notification_error,
            )
            for o in items
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


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
