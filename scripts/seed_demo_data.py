#!/usr/bin/env python3
"""
Regenera datos de demostración (Tienda Demo Paraguay + ~10 órdenes).

Uso local / Docker:
  python scripts/seed_demo_data.py
  docker compose run --rm web python scripts/seed_demo_data.py

Variables de entorno (opcionales):
  SEED_TN_LINK_MODE — `oauth_ready` (default) | `demo`.
    oauth_ready: sin TN hasta OAuth; evita conflict con demo-paraguay-tn.
    demo: id ficticio + token placeholder; no mezclar con OAuth a otra TN.
  SEED_STORE_EXTERNAL_ID — En demo default `demo-paraguay-tn`. En oauth_ready suele ir vacío.
  SEED_USER_EMAIL — Default demo@tiendademo.py (mismo email en cada wipe).
  SEED_USER_PASSWORD — Default Demo2026Pass!. En prod los merchants usan /register (MS-ONB02).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

# Proyecto raíz en PYTHONPATH (Docker WORKDIR /app)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv(".env.docker", override=False)
load_dotenv(".env", override=False)

from sqlalchemy.orm import Session

from backend.app.core.security import hash_password
from backend.app.db.session import SessionLocal
from backend.app.models.notification import NotificationAttempt
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser

DEFAULT_DEMO_EXTERNAL_ID = "demo-paraguay-tn"


def _wipe_store_cascade(db: Session, store_id: int) -> None:
    order_ids = [r[0] for r in db.query(Order.id).filter(Order.store_id == store_id).all()]
    if order_ids:
        db.query(NotificationAttempt).filter(NotificationAttempt.order_id.in_(order_ids)).delete(
            synchronize_session=False
        )
        db.query(Order).filter(Order.store_id == store_id).delete(synchronize_session=False)
    db.query(StoreUser).filter(StoreUser.store_id == store_id).delete(synchronize_session=False)
    db.query(StoreSettings).filter(StoreSettings.store_id == store_id).delete(
        synchronize_session=False
    )
    db.query(StoreInstallation).filter(StoreInstallation.store_id == store_id).delete(
        synchronize_session=False
    )
    st = db.query(Store).filter(Store.id == store_id).first()
    if st:
        db.delete(st)
    db.commit()


def wipe_seed_store(db: Session, user_email: str, legacy_external_id: str | None) -> None:
    """
    Elimina la tienda asociada al usuario seed (mismo email en cada corrida).
    Si no hay usuario, intenta borrar por external_id legado (migración desde seeds viejos).
    """
    user = db.query(StoreUser).filter(StoreUser.email == user_email).first()
    if user:
        _wipe_store_cascade(db, user.store_id)
        print(f"Tienda demo anterior eliminada (usuario seed {user_email}).")
        return
    if legacy_external_id:
        store = db.query(Store).filter(Store.external_store_id == legacy_external_id).first()
        if store:
            _wipe_store_cascade(db, store.id)
            print(f"Tienda demo anterior eliminada (external_id={legacy_external_id}).")


def seed() -> None:
    user_email = os.environ.get("SEED_USER_EMAIL", "demo@tiendademo.py")
    user_password = os.environ.get("SEED_USER_PASSWORD", "Demo2026Pass!")
    mode = os.environ.get("SEED_TN_LINK_MODE", "oauth_ready").strip().lower()
    if mode not in ("demo", "oauth_ready"):
        raise SystemExit(f"SEED_TN_LINK_MODE inválido: {mode!r} (usar demo u oauth_ready)")

    explicit_ext = os.environ.get("SEED_STORE_EXTERNAL_ID", "").strip()

    if mode == "demo":
        store_external_id = explicit_ext or DEFAULT_DEMO_EXTERNAL_ID
        tn_token = "SEED_DEMO_PLACEHOLDER"
        tn_active = True
        onboarding_st = "active"
    else:
        # oauth_ready
        store_external_id = explicit_ext if explicit_ext else None
        tn_token = ""
        tn_active = False
        onboarding_st = "pending"

    legacy_wipe_ext = None
    if mode == "demo":
        legacy_wipe_ext = store_external_id
    else:
        # también limpiar restos del seed antiguo demo-paraguay-tn si existían sin user
        legacy_wipe_ext = DEFAULT_DEMO_EXTERNAL_ID

    db = SessionLocal()
    try:
        wipe_seed_store(db, user_email, legacy_wipe_ext)

        now = datetime.utcnow()

        store = Store(
            name="Tienda Demo Paraguay",
            external_store_id=store_external_id,
            country="Paraguay",
            status="active",
        )
        db.add(store)
        db.flush()

        settings = StoreSettings(
            store_id=store.id,
            weraha_enabled=True,
            whatsapp_enabled=True,
            whatsapp_phone_number_id=os.environ.get("WHATSAPP_PHONE_NUMBER_ID") or "demo-phone-id",
            template_in_transit="shipping_in_transit_v1",
            template_delivered="shipping_delivered_v1",
            onboarding_status=onboarding_st,
        )
        db.add(settings)

        # Instalación TN: en oauth_ready fila vacía/inactiva para que needs_tiendanube sea True
        if mode == "demo":
            installation = StoreInstallation(
                store_id=store.id,
                order_source_type="tiendanube",
                access_token=tn_token,
                is_active=tn_active,
                installed_at=now,
            )
            db.add(installation)
        else:
            installation = StoreInstallation(
                store_id=store.id,
                order_source_type="tiendanube",
                access_token=tn_token or None,
                is_active=tn_active,
                installed_at=None,
            )
            db.add(installation)

        user = StoreUser(
            store_id=store.id,
            email=user_email,
            password_hash=hash_password(user_password),
            role="admin",
        )
        db.add(user)
        db.flush()

        demo_orders: list[dict] = [
            {
                "external_id": "TN-1001",
                "customer_name": "Ana Martinez",
                "phone": "+595981111001",
                "tracking": "WH-DEMO-1001",
                "status": "pending_tracking",
                "notif": None,
                "invalid": False,
            },
            {
                "external_id": "TN-1002",
                "customer_name": "Carlos Lopez",
                "phone": "+595981111002",
                "tracking": "WH-DEMO-1002",
                "status": "ready_for_polling",
                "notif": None,
                "invalid": False,
            },
            {
                "external_id": "TN-1003",
                "customer_name": "Maria Ferreira",
                "phone": "+595981111003",
                "tracking": "WH-DEMO-1003",
                "status": "in_transit",
                "notif": "pending",
                "invalid": False,
            },
            {
                "external_id": "TN-1004",
                "customer_name": "Pedro Benitez",
                "phone": "+595981111004",
                "tracking": "WH-DEMO-1004",
                "status": "delivered",
                "notif": "sent",
                "template": "shipping_delivered_v1",
                "preview": "Tu pedido #TN-1004 fue entregado. Gracias por tu compra.",
                "notified_delivered": True,
                "invalid": False,
            },
            {
                "external_id": "TN-1005",
                "customer_name": "Laura Gimenez",
                "phone": "+595981555005",
                "tracking": "WH-DEMO-1005",
                "status": "in_transit",
                "notif": "sent",
                "template": "hello_world",
                "preview": "Tu pedido #TN-1005 esta en camino",
                "notified_in_transit": True,
                "invalid": False,
            },
            {
                "external_id": "TN-1006",
                "customer_name": "Roberto Acosta",
                "phone": "invalid",
                "tracking": "WH-DEMO-1006",
                "status": "in_transit",
                "notif": None,
                "invalid": True,
            },
            {
                "external_id": "TN-1007",
                "customer_name": "Sofia Romero",
                "phone": "+595981111007",
                "tracking": "WH-DEMO-1007",
                "status": "delivered",
                "notif": "sent",
                "template": "shipping_delivered_v1",
                "preview": "Tu pedido #TN-1007 fue entregado.",
                "notified_delivered": True,
                "invalid": False,
            },
            {
                "external_id": "TN-1008",
                "customer_name": "Diego Villalba",
                "phone": "+595981111008",
                "tracking": "WH-DEMO-1008",
                "status": "in_transit",
                "notif": "failed",
                "error": "Error 131047: Re-engagement message required (usuario sin ventana 24h)",
                "invalid": False,
            },
            {
                "external_id": "TN-1009",
                "customer_name": "Lucia Nuñez",
                "phone": "+595981111009",
                "tracking": "WH-DEMO-1009",
                "status": "pending_tracking",
                "notif": None,
                "invalid": False,
            },
            {
                "external_id": "TN-1010",
                "customer_name": "Fernando Rios",
                "phone": "+595981111010",
                "tracking": "WH-DEMO-1010",
                "status": "delivered",
                "notif": "sent",
                "template": "shipping_delivered_v1",
                "preview": "Tu pedido #TN-1010 fue entregado.",
                "notified_delivered": True,
                "invalid": False,
            },
        ]

        for row in demo_orders:
            o = Order(
                store_id=store.id,
                external_id=row["external_id"],
                customer_name=row["customer_name"],
                raw_phone=row["phone"],
                normalized_phone=None if row["invalid"] else row["phone"],
                tracking_number=row["tracking"],
                tracking_url=f"https://weraha.example/track/{row['tracking']}",
                current_status=row["status"],
                invalid_phone=row["invalid"],
                notified_in_transit=row.get("notified_in_transit", False),
                notified_delivered=row.get("notified_delivered", False),
            )

            ns = row.get("notif")
            if ns == "sent":
                o.notification_status = "sent"
                o.last_template_name = row.get("template")
                o.last_message_preview = row.get("preview")
                o.last_message_type = "delivered" if row["status"] == "delivered" else "in_transit"
                t = now - timedelta(hours=2)
                o.first_notification_at = t
                o.last_notification_at = t
            elif ns == "failed":
                o.notification_status = "failed"
                o.notification_error = row.get("error", "send_failed")
                o.last_template_name = "shipping_in_transit_v1"
                o.last_message_preview = None
            elif ns == "pending":
                o.notification_status = "pending"
            else:
                o.notification_status = None

            db.add(o)

        db.flush()

        order_1005 = (
            db.query(Order)
            .filter(Order.store_id == store.id, Order.external_id == "TN-1005")
            .first()
        )
        if order_1005:
            db.add(
                NotificationAttempt(
                    store_id=store.id,
                    order_id=order_1005.id,
                    event_type="in_transit",
                    idempotency_key=f"{store.id}:{order_1005.id}:in_transit",
                    template_name="hello_world",
                    status="sent",
                    provider_message_id="wamid.demo_seed_placeholder",
                    attempt_number=1,
                )
            )

        db.commit()

        print("Seed completado.")
        print(f"  SEED_TN_LINK_MODE={mode}")
        print(f"  Tienda: {store.name} (external_store_id={store.external_store_id!r})")
        print(f"  Login panel: {user_email} / {user_password}")
        print("  Órdenes: TN-1001 … TN-1010 (mezcla de estados como en Heroku)")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
