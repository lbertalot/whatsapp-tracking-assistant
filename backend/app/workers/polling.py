import logging
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from backend.app.models.order import Order
from backend.app.models.store import Store, StoreSettings
from backend.app.services.notification import NotificationEngine
from backend.app.services.state_mapper import map_raw_status
from backend.app.services.weraha import WerahaAdapter

logger = logging.getLogger(__name__)

weraha_adapter = WerahaAdapter()
notification_engine = NotificationEngine()

TERMINAL_STATUSES = {"delivered", "notification_failed"}
POLLABLE_STATUSES = {"pending_tracking", "ready_for_polling", "in_transit"}


def get_eligible_orders(db: Session) -> List[Order]:
    active_store_ids = (
        db.query(Store.id)
        .join(StoreSettings, StoreSettings.store_id == Store.id)
        .filter(
            Store.status == "active",
            StoreSettings.onboarding_status == "active",
        )
        .scalar_subquery()
    )

    return (
        db.query(Order)
        .filter(
            Order.store_id.in_(active_store_ids),
            Order.tracking_number.isnot(None),
            Order.tracking_number != "",
            Order.current_status.in_(POLLABLE_STATUSES),
        )
        .all()
    )


def process_order(db: Session, order: Order) -> None:
    try:
        result = weraha_adapter.get_tracking_status(order.tracking_number)
        raw_status = result.get("status", "")
        mapped = map_raw_status(raw_status)

        order.last_checked_at = datetime.utcnow()

        if mapped and mapped != order.current_status:
            old_status = order.current_status
            order.current_status = mapped
            order.last_status_change_at = datetime.utcnow()
            db.commit()

            logger.info("Order %s status: %s -> %s", order.id, old_status, mapped)

            notif_result = notification_engine.evaluate_and_notify(db, order)
            if notif_result.get("sent"):
                logger.info("Order %s notified: %s", order.id, notif_result["event_type"])
        else:
            db.commit()

    except Exception:
        logger.exception("Error processing order %s", order.id)
        db.rollback()


def run_polling_cycle(db: Session) -> int:
    orders = get_eligible_orders(db)
    logger.info("Polling cycle: %d eligible orders", len(orders))

    for order in orders:
        process_order(db, order)

    return len(orders)
