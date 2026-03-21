import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.services.tiendanube import TiendanubeService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/integrations/tiendanube")

tn_service = TiendanubeService()


@router.get("/install")
def install():
    return RedirectResponse(url=tn_service.get_auth_url(), status_code=302)


@router.get("/callback")
def callback(code: str = Query(...), db: Session = Depends(get_db)):
    try:
        token_data = tn_service.exchange_code(code)
    except Exception as e:
        logger.error("TN OAuth code exchange failed: %s", e)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid authorization code")

    access_token = token_data["access_token"]
    user_id = str(token_data["user_id"])

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
        .filter(StoreInstallation.store_id == store.id, StoreInstallation.order_source_type == "tiendanube")
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

    logger.info("TN store %s installed/updated successfully", user_id)

    return {"status": "installed", "store_id": store.id, "external_store_id": user_id}
