import logging
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from backend.app.models.notification import NotificationAttempt
from backend.app.models.order import Order
from backend.app.services.whatsapp import WhatsAppService

logger = logging.getLogger(__name__)

TEMPLATE_MAP = {
    "in_transit": "shipping_in_transit_v1",
    "delivered": "shipping_delivered_v1",
}

PREVIEW_MAP = {
    "in_transit": "Tu pedido ya está en camino",
    "delivered": "Tu pedido fue entregado",
}


class NotificationEngine:
    def __init__(self, whatsapp: Optional[WhatsAppService] = None, max_retries: int = 1):
        self.whatsapp = whatsapp or WhatsAppService(mock=True)
        self.max_retries = max_retries

    def evaluate_and_notify(self, db: Session, order: Order) -> Dict:
        if order.invalid_phone:
            return {"sent": False, "reason": "invalid_phone"}

        event_type = self._get_pending_event(order)
        if event_type is None:
            return {"sent": False, "reason": "already_notified"}

        idempotency_key = f"{order.store_id}:{order.id}:{event_type}"

        existing = (
            db.query(NotificationAttempt)
            .filter(
                NotificationAttempt.idempotency_key == idempotency_key,
                NotificationAttempt.status == "sent",
            )
            .first()
        )
        if existing:
            return {"sent": False, "reason": "already_notified"}

        return self._send_with_retry(db, order, event_type, idempotency_key)

    def _get_pending_event(self, order: Order) -> Optional[str]:
        if order.current_status == "in_transit" and not order.notified_in_transit:
            return "in_transit"
        if order.current_status == "delivered" and not order.notified_delivered:
            return "delivered"
        return None

    def _send_with_retry(
        self, db: Session, order: Order, event_type: str, idempotency_key: str
    ) -> Dict:
        template_name = TEMPLATE_MAP.get(event_type, event_type)
        last_result = None

        for attempt_num in range(1, self.max_retries + 2):
            result = self.whatsapp.send_template_message(
                to=order.normalized_phone,
                template_name=template_name,
                params={"order_id": str(order.external_id)},
            )

            attempt = NotificationAttempt(
                store_id=order.store_id,
                order_id=order.id,
                event_type=event_type,
                idempotency_key=(
                    idempotency_key if attempt_num == 1
                    else f"{idempotency_key}:retry_{attempt_num}"
                ),
                template_name=template_name,
                status="sent" if result["success"] else "failed",
                provider_message_id=result.get("message_id"),
                error_code=result.get("error"),
                error_message=result.get("error_message"),
                attempt_number=attempt_num,
            )
            db.add(attempt)
            db.flush()

            if result["success"]:
                self._update_order_success(db, order, event_type, template_name)
                return {"sent": True, "event_type": event_type, "attempt": attempt_num}

            last_result = result

        self._update_order_failure(db, order, last_result)
        return {
            "sent": False,
            "reason": "send_failed",
            "event_type": event_type,
            "error": last_result.get("error_message"),
        }

    def _update_order_success(
        self, db: Session, order: Order, event_type: str, template_name: str
    ) -> None:
        now = datetime.utcnow()
        order.notification_status = "sent"
        order.last_message_type = event_type
        order.last_template_name = template_name
        order.last_message_preview = PREVIEW_MAP.get(event_type, "")
        order.last_notification_at = now

        if order.first_notification_at is None:
            order.first_notification_at = now

        if event_type == "in_transit":
            order.notified_in_transit = True
        elif event_type == "delivered":
            order.notified_delivered = True

        order.notification_error = None
        db.commit()

    def _update_order_failure(self, db: Session, order: Order, result: dict) -> None:
        order.notification_status = "failed"
        order.notification_error = result.get("error_message", "Unknown error")
        db.commit()
