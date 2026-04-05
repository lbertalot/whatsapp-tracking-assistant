"""Periodic reconciliation: fetch order state from Tiendanube (ecommerce source of truth)."""

import logging
import time
from datetime import datetime
from typing import List, Optional

from httpx import HTTPError
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.services.notification import NotificationEngine
from backend.app.services.tiendanube import TiendanubeService
from backend.app.services.tiendanube_order_status import (
    map_tiendanube_order_detail,
    tracking_from_order_detail,
)

logger = logging.getLogger(__name__)

tn_service = TiendanubeService()
notification_engine = NotificationEngine()

POLLABLE_STATUSES = {"pending_tracking", "in_transit"}


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


def get_eligible_orders(db: Session) -> List[Order]:
    active_store_ids = (
        db.query(Store.id)
        .join(StoreSettings, StoreSettings.store_id == Store.id)
        .filter(
            Store.status == "active",
            StoreSettings.onboarding_status == "active",
            StoreSettings.ecommerce_sync_enabled.is_(True),
        )
        .scalar_subquery()
    )

    return (
        db.query(Order)
        .filter(
            Order.store_id.in_(active_store_ids),
            Order.current_status.in_(POLLABLE_STATUSES),
        )
        .all()
    )


def process_order(db: Session, order: Order) -> None:
    try:
        inst = _tn_installation(db, order.store_id)
        if not inst:
            return

        store = db.query(Store).filter(Store.id == order.store_id).first()
        if not store or not store.external_store_id:
            return

        try:
            tn_user_id = int(store.external_store_id)
            oid = int(str(order.external_id))
        except (TypeError, ValueError):
            return

        token = inst.access_token.strip()
        try:
            detail = tn_service.fetch_order(
                tn_user_id,
                oid,
                token,
                aggregates="fulfillment_orders",
            )
        except (HTTPError, ValueError, TypeError) as e:
            logger.warning("TN sync fetch_order failed order=%s: %s", order.id, e)
            return

        track, _ = tracking_from_order_detail(detail)
        if track and not order.tracking_number:
            order.tracking_number = track

        merged = dict(detail)
        mapped = map_tiendanube_order_detail(merged)
        if mapped is None and order.tracking_number:
            mapped = "in_transit"

        raw = str(detail.get("shipping_status") or detail.get("status") or "")[:100] or None
        order.platform_status_raw = raw
        order.last_status_source = "sync"
        order.last_checked_at = datetime.utcnow()

        if mapped is None:
            db.commit()
            return

        old = order.current_status
        if mapped != old:
            order.current_status = mapped
            order.last_status_change_at = datetime.utcnow()
            logger.info("Order %s status sync: %s -> %s", order.id, old, mapped)

        db.commit()
        db.refresh(order)
        notification_engine.evaluate_and_notify(db, order)

    except Exception:
        logger.exception("Error processing order %s", order.id)
        db.rollback()


def run_polling_cycle(db: Session) -> int:
    orders = get_eligible_orders(db)
    logger.info("Ecommerce sync cycle: %d eligible orders", len(orders))

    for order in orders:
        process_order(db, order)

    return len(orders)


if __name__ == "__main__":
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    from backend.app.db.session import SessionLocal

    logger.info(
        "Worker starting (tiendanube sync, interval=%ds, wa_global_fallback=%s)",
        settings.POLL_INTERVAL_SECONDS,
        settings.WHATSAPP_ALLOW_GLOBAL_FALLBACK,
    )

    while True:
        db = SessionLocal()
        try:
            processed = run_polling_cycle(db)
            logger.info("Cycle complete: %d orders processed", processed)
        except Exception:
            logger.exception("Sync cycle failed")
        finally:
            db.close()

        time.sleep(settings.POLL_INTERVAL_SECONDS)
