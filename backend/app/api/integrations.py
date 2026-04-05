import logging
from typing import Optional
from urllib.parse import urljoin

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.core.dependencies import get_current_user
from backend.app.core.security import create_tn_oauth_state, decode_tn_oauth_state
from backend.app.db.session import get_db
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser
from backend.app.schemas.onboarding import TiendanubeInstallUrlResponse
from backend.app.services.tiendanube import TiendanubeService
from backend.app.services.tiendanube_initial_import import run_initial_orders_import_task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/tiendanube")
api_tn_router = APIRouter(prefix="/api/integrations/tiendanube", tags=["integrations"])

tn_service = TiendanubeService()


def _onboarding_redirect(query: str) -> RedirectResponse:
    base = settings.APP_BASE_URL.rstrip("/") + "/"
    return RedirectResponse(url=urljoin(base, f"onboarding?{query}"), status_code=302)


@api_tn_router.get("/install-url", response_model=TiendanubeInstallUrlResponse)
def install_url_authenticated(current_user: StoreUser = Depends(get_current_user)):
    """URL de autorización Tiendanube con `state` JWT vinculado al store del usuario logueado."""
    if (
        not (settings.TIENDANUBE_APP_ID or "").strip()
        or not (settings.TIENDANUBE_CLIENT_SECRET or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Tiendanube no está configurado en el servidor (faltan APP_ID o CLIENT_SECRET).",
        )
    state = create_tn_oauth_state(current_user.store_id)
    url = tn_service.get_auth_url(state=state)
    return TiendanubeInstallUrlResponse(url=url)


@router.get("/install")
def install():
    return RedirectResponse(url=tn_service.get_auth_url(), status_code=302)


@router.get("/callback")
def callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    try:
        token_data = tn_service.exchange_code(code)
    except Exception as e:
        logger.error("TN OAuth code exchange failed: %s", e)
        if state:
            return _onboarding_redirect("error=token_exchange")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid authorization code",
        )

    access_token = token_data["access_token"]
    user_id = str(token_data["user_id"])

    if state:
        payload = decode_tn_oauth_state(state)
        if not payload:
            logger.warning("TN OAuth callback: invalid or expired state")
            return _onboarding_redirect("error=invalid_state")

        store_id = payload.get("store_id")
        store = db.query(Store).filter(Store.id == store_id).first()
        if not store:
            logger.warning("TN OAuth callback: store_id %s not found", store_id)
            return _onboarding_redirect("error=unknown_store")

        if store.external_store_id and store.external_store_id != user_id:
            logger.warning(
                "TN OAuth store conflict: store %s has external_id %s, TN user %s",
                store.id,
                store.external_store_id,
                user_id,
            )
            return _onboarding_redirect("error=store_conflict")

        store.external_store_id = user_id
        try:
            info = tn_service.fetch_store_info(int(user_id), access_token)
            name = None
            if isinstance(info, dict):
                raw = info.get("name")
                if isinstance(raw, str):
                    name = raw
                elif isinstance(raw, dict):
                    name = raw.get("es") or raw.get("pt") or raw.get("en")
            if name:
                store.name = str(name)[:150]
        except Exception as e:
            logger.info("TN store name fetch skipped or failed: %s", e)

        settings_row = db.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
        if not settings_row:
            settings_row = StoreSettings(store_id=store.id, onboarding_status="active")
            db.add(settings_row)
            db.flush()
        else:
            settings_row.onboarding_status = "active"

        installation = (
            db.query(StoreInstallation)
            .filter(
                StoreInstallation.store_id == store.id,
                StoreInstallation.order_source_type == "tiendanube",
            )
            .first()
        )

        if installation:
            installation.access_token = access_token
            installation.is_active = True
        else:
            installation = StoreInstallation(
                store_id=store.id,
                order_source_type="tiendanube",
                access_token=access_token,
                is_active=True,
            )
            db.add(installation)

        db.commit()

        background_tasks.add_task(run_initial_orders_import_task, store.id)

        try:
            tn_service.register_webhooks(int(user_id), access_token)
        except Exception as e:
            logger.warning("TN register_webhooks after onboarding: %s", e)

        logger.info("TN store linked to panel store_id=%s tn_user_id=%s", store.id, user_id)
        return _onboarding_redirect("success=1")

    # Legacy: instalación desde Tiendanube sin flujo panel (sin state)
    store = db.query(Store).filter(Store.external_store_id == user_id).first()
    if not store:
        store = Store(
            external_store_id=user_id,
            name=f"Tiendanube #{user_id}",
            status="active",
        )
        db.add(store)
        db.flush()

        store_settings = StoreSettings(store_id=store.id, onboarding_status="pending")
        db.add(store_settings)

    installation = (
        db.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store.id,
            StoreInstallation.order_source_type == "tiendanube",
        )
        .first()
    )

    if installation:
        installation.access_token = access_token
        installation.is_active = True
    else:
        installation = StoreInstallation(
            store_id=store.id,
            order_source_type="tiendanube",
            access_token=access_token,
            is_active=True,
        )
        db.add(installation)

    db.commit()

    background_tasks.add_task(run_initial_orders_import_task, store.id)

    logger.info("TN store %s installed/updated (legacy, no state)", user_id)

    return {"status": "installed", "store_id": store.id, "external_store_id": user_id}
