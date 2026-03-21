from fastapi import APIRouter, Depends
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.order import Order

router = APIRouter()


@router.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/ready")
def readiness_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unavailable"

    return {"status": "ok", "database": db_status}


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)):
    total = db.query(func.count(Order.id)).scalar() or 0
    notified = (
        db.query(func.count(Order.id))
        .filter(Order.first_notification_at.isnot(None))
        .scalar() or 0
    )
    invalid_phone = (
        db.query(func.count(Order.id))
        .filter(Order.invalid_phone.is_(True))
        .scalar() or 0
    )
    wa_errors = (
        db.query(func.count(Order.id))
        .filter(Order.notification_status == "failed")
        .scalar() or 0
    )

    pct = lambda n, d: round((n / d) * 100, 1) if d > 0 else 0.0

    return {
        "total_orders": total,
        "orders_notified": notified,
        "pct_notified": pct(notified, total),
        "orders_invalid_phone": invalid_phone,
        "pct_invalid_phone": pct(invalid_phone, total),
        "orders_whatsapp_errors": wa_errors,
        "pct_whatsapp_errors": pct(wa_errors, total),
    }
