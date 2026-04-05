import hashlib
import hmac
import json
import logging
from datetime import datetime
from typing import Any, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from httpx import HTTPError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.services.notification import NotificationEngine
from backend.app.services.phone import default_region_for_store, normalize_phone
from backend.app.services.tiendanube import TiendanubeService
from backend.app.services.tiendanube_order_detail import customer_fields_from_order_detail
from backend.app.services.tiendanube_order_status import (
    ecommerce_order_cancelled,
    map_tiendanube_order_detail,
    tracking_from_order_detail,
)

logger = logging.getLogger(__name__)

router = APIRouter()
tn_service = TiendanubeService()
notification_engine = NotificationEngine()

LGPD_EVENTS = {"store/redact", "customers/redact", "customers/data_request"}
ORDER_CREATE_EVENTS = {"order/created", "order/paid"}
ORDER_FULFILLED = "order/fulfilled"
ORDER_EVENTS = ORDER_CREATE_EVENTS | {ORDER_FULFILLED}


def _verify_tn_hmac(body_bytes: bytes, signature: Optional[str]) -> bool:
    if not signature:
        return False
    expected = hmac.new(
        settings.TIENDANUBE_CLIENT_SECRET.encode(),
        body_bytes,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _tn_installation(db: Session, store_id: int) -> Optional[StoreInstallation]:
    row = (
        db.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store_id,
            StoreInstallation.order_source_type == "tiendanube",
            StoreInstallation.is_active.is_(True),
        )
        .first()
    )
    if row and row.access_token and str(row.access_token).strip():
        return row
    return None


def _tracking_from_webhook_payload(
    payload: dict,
) -> Tuple[Optional[str], Optional[str]]:
    track = payload.get("shipping_tracking_number")
    url = payload.get("shipping_tracking_url")
    if track:
        return str(track), url if isinstance(url, str) else None
    ti = payload.get("tracking_info")
    if isinstance(ti, dict) and ti.get("code"):
        return str(ti["code"]), (ti.get("url") if isinstance(ti.get("url"), str) else None)
    return None, None


def _store_settings_row(db: Session, store_id: int) -> Optional[StoreSettings]:
    return db.query(StoreSettings).filter(StoreSettings.store_id == store_id).first()


@router.post("/webhooks/tiendanube")
async def tiendanube_webhook(request: Request, db: Session = Depends(get_db)):
    body_bytes = await request.body()
    signature = request.headers.get("X-Linkedstore-Hmac-Sha256")

    if not _verify_tn_hmac(body_bytes, signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC")

    payload: dict[str, Any] = json.loads(body_bytes)
    event = payload.get("event", "")

    if event in LGPD_EVENTS:
        return _handle_lgpd(db, event, payload)

    if event not in ORDER_EVENTS:
        return {"status": "ignored", "event": event}

    store_id_ext = str(payload.get("store_id", ""))
    store = db.query(Store).filter(Store.external_store_id == store_id_ext).first()
    if not store:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Store not found")

    installation = _tn_installation(db, store.id)
    if not installation:
        logger.warning("TN webhook: no access_token for store_id=%s event=%s", store.id, event)
        return {"status": "ignored", "reason": "no_access_token", "event": event}

    try:
        tn_user_id = int(store.external_store_id or "0")
    except (TypeError, ValueError):
        logger.warning("TN webhook: invalid external_store_id for store %s", store.id)
        return {"status": "ignored", "reason": "invalid_tn_user_id", "event": event}

    order_ext_id = str(payload.get("id", ""))
    if not order_ext_id:
        return {"status": "ignored", "reason": "missing_order_id", "event": event}

    existing = (
        db.query(Order)
        .filter(Order.store_id == store.id, Order.external_id == order_ext_id)
        .first()
    )

    token = installation.access_token.strip()

    if event == ORDER_FULFILLED:
        return _handle_order_fulfilled(
            db,
            store=store,
            existing=existing,
            order_ext_id=order_ext_id,
            tn_user_id=tn_user_id,
            access_token=token,
            payload=payload,
        )

    # order/created, order/paid
    return _handle_order_create_or_paid(
        db,
        store=store,
        existing=existing,
        order_ext_id=order_ext_id,
        tn_user_id=tn_user_id,
        access_token=token,
    )


def _handle_lgpd(db: Session, event: str, payload: dict) -> dict:
    if event == "store/redact":
        sid = payload.get("store_id")
        store_id_ext = str(sid) if sid is not None else ""
        store = db.query(Store).filter(Store.external_store_id == store_id_ext).first()
        if store:
            store.status = "redacted"
            for inst in store.installations:
                inst.is_active = False
            db.commit()
            logger.info("store/redact applied: store_id=%s", store.id)
        else:
            logger.info("store/redact: unknown TN store_id=%s (ack)", store_id_ext)
        return {"status": "acknowledged", "event": event}

    logger.info("LGPD event received: %s for store %s", event, payload.get("store_id"))
    return {"status": "acknowledged", "event": event}


def _handle_order_create_or_paid(
    db: Session,
    *,
    store: Store,
    existing: Optional[Order],
    order_ext_id: str,
    tn_user_id: int,
    access_token: str,
) -> dict:
    if existing:
        return {"status": "received", "order_id": existing.id}

    try:
        oid = int(order_ext_id)
        detail = tn_service.fetch_order(tn_user_id, oid, access_token, aggregates=None)
    except (HTTPError, ValueError, TypeError) as e:
        logger.error("TN fetch_order failed store=%s order=%s: %s", store.id, order_ext_id, e)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Temporary failure fetching order from Tiendanube",
        ) from e

    raw_phone, name = customer_fields_from_order_detail(detail)
    st = _store_settings_row(db, store.id)
    region = default_region_for_store(store, st)
    normalized = normalize_phone(raw_phone, region)
    is_invalid = raw_phone is not None and normalized is None

    order = Order(
        store_id=store.id,
        external_id=order_ext_id,
        customer_name=name,
        raw_phone=raw_phone,
        normalized_phone=normalized,
        invalid_phone=is_invalid,
        tracking_number=None,
        tracking_url=None,
        current_status="pending_tracking",
        last_status_source="webhook",
        platform_status_raw=(str(detail.get("status") or "")[:100] or None),
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info("TN order %s ingested from API for store %s", order.id, store.id)
    return {"status": "received", "order_id": order.id}


def _tn_platform_snapshot(payload: dict, detail: Optional[dict], tracking: Optional[str]) -> str:
    if detail:
        return (str(detail.get("shipping_status") or detail.get("status") or "")[:100]) or "unknown"
    if tracking:
        return str(payload.get("shipping_status") or "shipped")[:100]
    return "unknown"


def _transition_order_from_tn(
    db: Session,
    order: Order,
    *,
    detail: Optional[dict],
    payload: dict,
    tracking: Optional[str],
) -> None:
    """Set status from ecommerce payload; notify on status advance or pending templates."""
    merged: dict[str, Any] = dict(detail) if detail else {}
    if tracking and not merged.get("fulfillment_orders"):
        merged = {
            **merged,
            "shipping_status": merged.get("shipping_status")
            or payload.get("shipping_status")
            or "shipped",
            "fulfillment_orders": [{"tracking_info": {"code": tracking}}],
        }
    mapped = map_tiendanube_order_detail(merged, order_id=order.id)
    if mapped is None and tracking and not ecommerce_order_cancelled(merged):
        mapped = "in_transit"
    if mapped is None:
        db.commit()
        return

    order.platform_status_raw = _tn_platform_snapshot(payload, detail, tracking)
    order.last_status_source = "webhook"
    old = order.current_status
    if mapped != old:
        order.current_status = mapped
        order.last_status_change_at = datetime.utcnow()
    db.commit()
    try:
        notification_engine.evaluate_and_notify(db, order)
    except Exception:
        logger.exception(
            "evaluate_and_notify failed after TN transition (order_id=%s store_id=%s)",
            order.id,
            order.store_id,
        )


def _handle_order_fulfilled(
    db: Session,
    *,
    store: Store,
    existing: Optional[Order],
    order_ext_id: str,
    tn_user_id: int,
    access_token: str,
    payload: dict,
) -> dict:
    w_track, w_url = _tracking_from_webhook_payload(payload)

    # Orden ya existe y el webhook trae tracking: actualizar sin llamar a la API (< 3s TN).
    if existing and w_track:
        existing.tracking_number = w_track
        existing.tracking_url = w_url
        _transition_order_from_tn(db, existing, detail=None, payload=payload, tracking=w_track)
        logger.info("Order %s tracking updated from webhook: %s", existing.id, w_track)
        return {"status": "received", "order_id": existing.id, "tracking_updated": True}

    detail: Optional[dict] = None
    if existing:
        try:
            oid = int(order_ext_id)
            detail = tn_service.fetch_order(
                tn_user_id,
                oid,
                access_token,
                aggregates="fulfillment_orders",
            )
        except (HTTPError, ValueError, TypeError) as e:
            logger.warning(
                "TN fetch_order (fulfilled) failed store=%s order=%s: %s",
                store.id,
                order_ext_id,
                e,
            )

    api_track, api_url = tracking_from_order_detail(detail) if detail else (None, None)
    tracking = w_track or api_track
    tracking_url = w_url or api_url

    if existing:
        if tracking:
            existing.tracking_number = tracking
            existing.tracking_url = tracking_url
            _transition_order_from_tn(
                db, existing, detail=detail, payload=payload, tracking=tracking
            )
            logger.info("Order %s tracking updated: %s", existing.id, tracking)
            return {
                "status": "received",
                "order_id": existing.id,
                "tracking_updated": True,
            }
        return {
            "status": "received",
            "order_id": existing.id,
            "tracking_updated": False,
        }

    # Orden aún no existe: crear desde API (p.ej. fulfilled antes que created en cola TN)
    if not detail:
        try:
            oid = int(order_ext_id)
            detail = tn_service.fetch_order(
                tn_user_id,
                oid,
                access_token,
                aggregates="fulfillment_orders" if not w_track else None,
            )
        except (HTTPError, ValueError, TypeError) as e:
            logger.error("TN fetch_order for new order on fulfilled failed: %s", e)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Temporary failure fetching order from Tiendanube",
            ) from e

    if not w_track:
        api_track2, api_url2 = tracking_from_order_detail(detail)
        tracking = tracking or api_track2
        tracking_url = tracking_url or api_url2

    raw_phone, name = customer_fields_from_order_detail(detail)
    st = _store_settings_row(db, store.id)
    region = default_region_for_store(store, st)
    normalized = normalize_phone(raw_phone, region)
    is_invalid = raw_phone is not None and normalized is None

    merged = dict(detail)
    mapped = map_tiendanube_order_detail(merged, order_id=None)
    if mapped is None and tracking and not ecommerce_order_cancelled(merged):
        mapped = "in_transit"
    initial = mapped or ("pending_tracking" if not tracking else "in_transit")

    order = Order(
        store_id=store.id,
        external_id=order_ext_id,
        customer_name=name,
        raw_phone=raw_phone,
        normalized_phone=normalized,
        invalid_phone=is_invalid,
        tracking_number=tracking,
        tracking_url=tracking_url,
        current_status=initial,
        platform_status_raw=_tn_platform_snapshot({}, detail, tracking),
        last_status_source="webhook",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    if mapped:
        notification_engine.evaluate_and_notify(db, order)
    logger.info("TN order %s created on fulfilled event for store %s", order.id, store.id)
    return {
        "status": "received",
        "order_id": order.id,
        "tracking_updated": bool(tracking),
    }
