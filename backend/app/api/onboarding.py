from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.db.session import get_db
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser
from backend.app.schemas.onboarding import OnboardingStatusResponse

router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


@router.get("/status", response_model=OnboardingStatusResponse)
def onboarding_status(
    db: Session = Depends(get_db),
    current_user: StoreUser = Depends(get_current_user),
):
    base = settings.APP_BASE_URL.rstrip("/")
    oauth_cb = f"{base}/integrations/tiendanube/callback"
    wh_url = f"{base}/webhooks/tiendanube"
    tn_ok = bool(
        (settings.TIENDANUBE_APP_ID or "").strip()
        and (settings.TIENDANUBE_CLIENT_SECRET or "").strip()
    )

    store = db.query(Store).filter(Store.id == current_user.store_id).first()
    if not store:
        return OnboardingStatusResponse(
            needs_tiendanube=True,
            tiendanube_user_id=None,
            installation_active=False,
            onboarding_status="pending",
            store_name="",
            initial_orders_import_completed=False,
            oauth_callback_url=oauth_cb,
            webhook_public_url=wh_url,
            tiendanube_app_configured=tn_ok,
        )

    inst = (
        db.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store.id,
            StoreInstallation.order_source_type == "tiendanube",
        )
        .first()
    )

    has_token = bool(inst and inst.is_active and (inst.access_token or "").strip())

    settings_row = db.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    onboarding_st = settings_row.onboarding_status if settings_row else "pending"
    import_done = bool(settings_row and settings_row.tn_initial_import_completed_at is not None)

    return OnboardingStatusResponse(
        needs_tiendanube=not has_token,
        tiendanube_user_id=store.external_store_id,
        installation_active=bool(inst and inst.is_active and (inst.access_token or "").strip()),
        onboarding_status=onboarding_st or "pending",
        store_name=store.name or "",
        initial_orders_import_completed=import_done,
        oauth_callback_url=oauth_cb,
        webhook_public_url=wh_url,
        tiendanube_app_configured=tn_ok,
    )
