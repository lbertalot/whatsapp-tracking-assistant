import secrets
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.order import Order

router = APIRouter()


def _metrics_key_valid(provided: Optional[str], expected: str) -> bool:
    if not expected or not provided:
        return False
    if len(provided) != len(expected):
        return False
    return secrets.compare_digest(
        provided.encode("utf-8"),
        expected.encode("utf-8"),
    )


def _pct(n: int, d: int) -> float:
    return round((n / d) * 100, 1) if d > 0 else 0.0


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
def metrics(
    db: Session = Depends(get_db),
    x_metrics_key: Optional[str] = Header(None, alias="X-Metrics-Key"),
):
    required = (settings.METRICS_API_KEY or "").strip()
    if required and not _metrics_key_valid(x_metrics_key, required):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    total = db.query(func.count(Order.id)).scalar() or 0
    notified = (
        db.query(func.count(Order.id)).filter(Order.first_notification_at.isnot(None)).scalar() or 0
    )
    invalid_phone = (
        db.query(func.count(Order.id)).filter(Order.invalid_phone.is_(True)).scalar() or 0
    )
    wa_errors = (
        db.query(func.count(Order.id)).filter(Order.notification_status == "failed").scalar() or 0
    )

    return {
        "total_orders": total,
        "orders_notified": notified,
        "pct_notified": _pct(notified, total),
        "orders_invalid_phone": invalid_phone,
        "pct_invalid_phone": _pct(invalid_phone, total),
        "orders_whatsapp_errors": wa_errors,
        "pct_whatsapp_errors": _pct(wa_errors, total),
    }
