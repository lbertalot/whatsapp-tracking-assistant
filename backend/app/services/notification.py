import logging
import time
from datetime import datetime
from typing import Dict, Optional

from sqlalchemy.orm import Session

from backend.app.models.notification import NotificationAttempt
from backend.app.models.order import Order
from backend.app.models.store import StoreSettings
from backend.app.services.whatsapp import WhatsAppService, graph_send_error_may_benefit_from_retry

logger = logging.getLogger(__name__)


def _store_whatsapp_notifications_enabled(st: Optional[StoreSettings]) -> bool:
    """False solo si la tienda desactivó explícitamente; None en BD legacy = habilitado."""
    if st is None:
        return True
    if st.whatsapp_enabled is None:
        return True
    return bool(st.whatsapp_enabled)


def _store_include_template_body_params(st: Optional[StoreSettings]) -> bool:
    """Si False, enviar plantilla sin `components` (útil si Meta no tiene variables en el body)."""
    if st is None:
        return True
    if getattr(st, "whatsapp_include_body_params", None) is None:
        return True
    return bool(st.whatsapp_include_body_params)


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
        self._whatsapp_override = whatsapp
        self.max_retries = max_retries

    def _whatsapp(self, db: Session, store_id: int) -> WhatsAppService:
        if self._whatsapp_override is not None:
            return self._whatsapp_override
        return WhatsAppService.resolve_for_store(db, store_id)

    def evaluate_and_notify(self, db: Session, order: Order) -> Dict:
        if order.invalid_phone:
            return {"sent": False, "reason": "invalid_phone"}

        event_type = self._get_pending_event(order)
        if event_type is None:
            return {"sent": False, "reason": "already_notified"}

        st = db.query(StoreSettings).filter(StoreSettings.store_id == order.store_id).first()
        if not _store_whatsapp_notifications_enabled(st):
            return {"sent": False, "reason": "whatsapp_disabled"}

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

        return self._send_with_retry(db, order, event_type, idempotency_key, store_settings=st)

    def _get_pending_event(self, order: Order) -> Optional[str]:
        if order.current_status == "in_transit" and not order.notified_in_transit:
            return "in_transit"
        if order.current_status == "delivered" and not order.notified_delivered:
            return "delivered"
        return None

    def _send_with_retry(
        self,
        db: Session,
        order: Order,
        event_type: str,
        idempotency_key: str,
        *,
        store_settings: Optional[StoreSettings] = None,
    ) -> Dict:
        st = store_settings
        if st is None:
            st = db.query(StoreSettings).filter(StoreSettings.store_id == order.store_id).first()
        include_body = _store_include_template_body_params(st)
        if include_body:
            oid = str(order.external_id)
            if st and getattr(st, "whatsapp_include_customer_name_in_body", False):
                name = (order.customer_name or "").strip() or "Cliente"
                template_params = {"customer_name": name, "order_id": oid}
            else:
                template_params = {"order_id": oid}
        else:
            template_params = {}

        template_name = TEMPLATE_MAP.get(event_type, event_type)
        if st:
            if event_type == "in_transit" and (st.template_in_transit or "").strip():
                template_name = st.template_in_transit.strip()
            elif event_type == "delivered" and (st.template_delivered or "").strip():
                template_name = st.template_delivered.strip()

        last_result = None
        max_attempts = self.max_retries + 1

        for attempt_num in range(1, max_attempts + 1):
            wa = self._whatsapp(db, order.store_id)
            result = wa.send_template_message(
                to=order.normalized_phone,
                template_name=template_name,
                params=template_params,
            )

            row_key = (
                idempotency_key
                if attempt_num == 1
                else f"{idempotency_key}:retry_{attempt_num}"
            )
            self._record_notification_attempt(
                db,
                order=order,
                event_type=event_type,
                idempotency_key=row_key,
                template_name=template_name,
                attempt_num=attempt_num,
                result=result,
            )

            if result["success"]:
                self._update_order_success(db, order, event_type, template_name)
                return {"sent": True, "event_type": event_type, "attempt": attempt_num}

            last_result = result

            if attempt_num < max_attempts and not result["success"]:
                if not graph_send_error_may_benefit_from_retry(result):
                    break
                ra = result.get("retry_after")
                if ra is not None:
                    try:
                        delay = min(int(str(ra).strip()), 120)
                        delay = max(delay, 1)
                    except (ValueError, TypeError):
                        delay = 2
                    logger.info(
                        "WhatsApp rate limit / retry: esperando %ss antes del reintento %s/%s",
                        delay,
                        attempt_num + 1,
                        max_attempts,
                    )
                    time.sleep(delay)

        self._update_order_failure(db, order, last_result)
        return {
            "sent": False,
            "reason": "send_failed",
            "event_type": event_type,
            "error": last_result.get("error_message") if last_result else None,
        }

    def _record_notification_attempt(
        self,
        db: Session,
        *,
        order: Order,
        event_type: str,
        idempotency_key: str,
        template_name: str,
        attempt_num: int,
        result: dict,
    ) -> None:
        """Inserta o actualiza la fila por ``idempotency_key`` (reintentos entre ciclos del worker)."""
        status = "sent" if result["success"] else "failed"
        existing = (
            db.query(NotificationAttempt)
            .filter(NotificationAttempt.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            if existing.status == "sent" and not result["success"]:
                logger.warning(
                    "Not overwriting sent notification_attempt with failure (key=%s)",
                    idempotency_key,
                )
                db.flush()
                return
            prev_status = existing.status
            existing.template_name = template_name
            existing.status = status
            existing.provider_message_id = result.get("message_id")
            existing.error_code = result.get("error")
            existing.error_message = result.get("error_message")
            if prev_status == "failed" and status == "failed":
                existing.attempt_number = (existing.attempt_number or 0) + 1
            else:
                existing.attempt_number = attempt_num
        else:
            db.add(
                NotificationAttempt(
                    store_id=order.store_id,
                    order_id=order.id,
                    event_type=event_type,
                    idempotency_key=idempotency_key,
                    template_name=template_name,
                    status=status,
                    provider_message_id=result.get("message_id"),
                    error_code=result.get("error"),
                    error_message=result.get("error_message"),
                    attempt_number=attempt_num,
                )
            )
        db.flush()

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
