from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.app.core.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.order import Order
from backend.app.models.store import StoreSettings
from backend.app.models.user import StoreUser
from backend.app.schemas.settings import StoreSettingsResponse, StoreSettingsUpdate

router = APIRouter()


@router.get("/panel/stats")
def panel_stats(
    db: Session = Depends(get_db),
    current_user: StoreUser = Depends(get_current_user),
):
    sid = current_user.store_id
    total = db.query(func.count(Order.id)).filter(Order.store_id == sid).scalar() or 0
    notified = (
        db.query(func.count(Order.id))
        .filter(Order.store_id == sid, Order.first_notification_at.isnot(None))
        .scalar() or 0
    )
    errors = (
        db.query(func.count(Order.id))
        .filter(Order.store_id == sid, Order.notification_status == "failed")
        .scalar() or 0
    )
    invalid = (
        db.query(func.count(Order.id))
        .filter(Order.store_id == sid, Order.invalid_phone.is_(True))
        .scalar() or 0
    )

    pct = lambda n, d: round((n / d) * 100, 1) if d > 0 else 0.0

    return {
        "total_orders": total,
        "orders_notified": notified,
        "pct_notified": pct(notified, total),
        "orders_errors": errors,
        "pct_errors": pct(errors, total),
        "orders_invalid_phone": invalid,
        "pct_invalid_phone": pct(invalid, total),
    }


@router.get("/api/settings", response_model=StoreSettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    current_user: StoreUser = Depends(get_current_user),
):
    settings = (
        db.query(StoreSettings)
        .filter(StoreSettings.store_id == current_user.store_id)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")
    return StoreSettingsResponse.from_store_settings(settings)


@router.put("/api/settings", response_model=StoreSettingsResponse)
def update_settings(
    body: StoreSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: StoreUser = Depends(get_current_user),
):
    settings = (
        db.query(StoreSettings)
        .filter(StoreSettings.store_id == current_user.store_id)
        .first()
    )
    if not settings:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Settings not found")

    update_data = body.model_dump(exclude_unset=True)
    if "whatsapp_access_token" in update_data:
        tok = update_data.pop("whatsapp_access_token")
        if tok == "":
            settings.whatsapp_access_token = None
        elif tok is not None:
            settings.whatsapp_access_token = tok

    for key, value in update_data.items():
        setattr(settings, key, value)

    db.commit()
    db.refresh(settings)
    return StoreSettingsResponse.from_store_settings(settings)
