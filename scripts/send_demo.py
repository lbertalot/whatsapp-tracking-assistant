"""
One-off script: send a real WhatsApp message to a test number
and update the order state in the Heroku Postgres DB.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from backend.app.db.session import SessionLocal
from backend.app.models.notification import NotificationAttempt
from backend.app.models.order import Order
from backend.app.services.whatsapp import WhatsAppService

TARGET_PHONE = "+5491112345678"
TEMPLATE_NAME = "hello_world"
TEMPLATE_LANG = "en_US"


def main():
    db = SessionLocal()

    order = (
        db.query(Order)
        .filter(
            Order.current_status == "in_transit",
            Order.notified_in_transit.is_(False),
        )
        .first()
    )

    if not order:
        print("No se encontro una orden in_transit sin notificar.")
        db.close()
        return

    print(
        f"Orden seleccionada: id={order.id}, external_id={order.external_id}, "
        f"cliente={order.customer_name}, telefono_actual={order.normalized_phone}"
    )

    order.normalized_phone = TARGET_PHONE
    order.invalid_phone = False
    db.commit()
    print(f"Telefono actualizado a {TARGET_PHONE}")

    wa = WhatsAppService(mock=False)
    print(f"Enviando template '{TEMPLATE_NAME}' ({TEMPLATE_LANG}) a {TARGET_PHONE}...")

    result = wa.send_template_message(
        to=TARGET_PHONE.replace("+", ""),
        template_name=TEMPLATE_NAME,
        language=TEMPLATE_LANG,
    )

    print(f"Resultado API: {result}")

    now = datetime.utcnow()
    idempotency_key = f"{order.store_id}:{order.id}:in_transit"

    existing = (
        db.query(NotificationAttempt)
        .filter(NotificationAttempt.idempotency_key == idempotency_key)
        .first()
    )
    if existing:
        idempotency_key = f"{idempotency_key}:demo_{now.strftime('%H%M%S')}"

    attempt = NotificationAttempt(
        store_id=order.store_id,
        order_id=order.id,
        event_type="in_transit",
        idempotency_key=idempotency_key,
        template_name=TEMPLATE_NAME,
        status="sent" if result["success"] else "failed",
        provider_message_id=result.get("message_id"),
        error_code=result.get("error"),
        error_message=result.get("error_message"),
        attempt_number=1,
    )
    db.add(attempt)

    if result["success"]:
        order.notification_status = "sent"
        order.notified_in_transit = True
        order.last_message_type = "in_transit"
        order.last_template_name = TEMPLATE_NAME
        order.last_message_preview = "Hello World - WhatsApp test message"
        order.first_notification_at = order.first_notification_at or now
        order.last_notification_at = now
        order.notification_error = None
        print("Orden actualizada: notification_status=sent, notified_in_transit=True")
    else:
        order.notification_status = "failed"
        order.notification_error = result.get("error_message", "Unknown error")
        print(f"FALLO: {result.get('error_message')}")

    db.commit()
    db.close()

    if result["success"]:
        print("\nMensaje enviado exitosamente.")
        print(f"  message_id: {result['message_id']}")
        print(f"  Revisa tu WhatsApp en {TARGET_PHONE}")
        print("  Revisa el panel: https://your-app.herokuapp.com/panel")
    else:
        print("\nEl envio fallo. Revisa las credenciales de Meta.")


if __name__ == "__main__":
    main()
