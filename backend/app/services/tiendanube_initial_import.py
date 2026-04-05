"""MS-ONB03: bulk import of recent Tiendanube orders after first OAuth link."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.services.phone import default_region_for_store, normalize_phone
from backend.app.services.tiendanube import TiendanubeService
from backend.app.services.tiendanube_order_detail import customer_fields_from_order_detail
from backend.app.services.tiendanube_order_status import (
    ecommerce_order_cancelled,
    map_tiendanube_order_detail,
    tracking_from_order_detail,
)

logger = logging.getLogger(__name__)

tn_service = TiendanubeService()


def _tn_installation(db: Session, store_id: int) -> Optional[StoreInstallation]:
    row = (
        db.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store_id,
            StoreInstallation.order_source_type == "tiendanube",
            StoreInstallation.is_active.is_(True),
        )
        .first()
    )
    if row and row.access_token and str(row.access_token).strip():
        return row
    return None


def create_order_from_onboarding_detail(
    db: Session,
    store: Store,
    detail: dict,
    *,
    phone_region: Optional[str] = None,
) -> Optional[Order]:
    """
    Stage a local Order from TN list/detail JSON. Skips duplicates.
    Does not commit — caller batches one commit after the import loop.
    Does not call WhatsApp — historical rows are marked as already notified.
    If ``phone_region`` is None, resolves region from StoreSettings once (for isolated tests).
    """
    oid = detail.get("id")
    if oid is None:
        return None
    order_ext_id = str(oid).strip()
    if not order_ext_id:
        return None

    existing = (
        db.query(Order)
        .filter(Order.store_id == store.id, Order.external_id == order_ext_id)
        .first()
    )
    if existing:
        return None

    raw_phone, name = customer_fields_from_order_detail(detail)
    if phone_region is not None:
        region = phone_region
    else:
        st = db.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
        region = default_region_for_store(store, st)
    normalized = normalize_phone(raw_phone, region)
    is_invalid = raw_phone is not None and normalized is None

    track, tracking_url = tracking_from_order_detail(detail)
    merged = dict(detail)
    mapped = map_tiendanube_order_detail(merged, order_id=None)
    if mapped is None and track and not ecommerce_order_cancelled(merged):
        mapped = "in_transit"
    initial = mapped or ("pending_tracking" if not track else "in_transit")

    platform_raw = str(detail.get("shipping_status") or detail.get("status") or "")[:100] or None

    # MS-ONB03: historical bulk import must not blast WhatsApp for past orders. We mark both
    # notification gates so the engine skips templates for this snapshot; live webhooks/worker
    # still update status and can notify on genuine forward transitions for rows also tracked live.
    order = Order(
        store_id=store.id,
        external_id=order_ext_id,
        customer_name=name,
        raw_phone=raw_phone,
        normalized_phone=normalized,
        invalid_phone=is_invalid,
        tracking_number=track,
        tracking_url=tracking_url,
        current_status=initial,
        platform_status_raw=platform_raw,
        last_status_source="onboarding_import",
        notified_in_transit=True,
        notified_delivered=True,
    )
    db.add(order)
    db.flush()
    return order


def run_initial_orders_import_in_session(db: Session, store_id: int) -> None:
    """
    Fetch up to TN_ONBOARDING_IMPORT_LIMIT recent orders and persist new rows.
    Sets tn_initial_import_completed_at on success (including zero orders).
    Caller must hold a DB session; commits inside.
    """
    st_check = db.query(StoreSettings).filter(StoreSettings.store_id == store_id).first()
    if st_check and st_check.tn_initial_import_completed_at is not None:
        logger.debug("TN initial import skipped: already completed store_id=%s", store_id)
        return

    store = db.query(Store).filter(Store.id == store_id).first()
    if not store or not store.external_store_id:
        logger.warning(
            "TN initial import skipped: missing store or external_store_id id=%s", store_id
        )
        return

    inst = _tn_installation(db, store_id)
    if not inst:
        logger.warning("TN initial import skipped: no installation store_id=%s", store_id)
        return

    try:
        tn_user_id = int(store.external_store_id)
    except (TypeError, ValueError):
        logger.warning("TN initial import skipped: invalid TN user id store_id=%s", store_id)
        return

    # Env TN_ONBOARDING_IMPORT_LIMIT (default 100); TN API allows up to 200 per page.
    limit = min(max(settings.TN_ONBOARDING_IMPORT_LIMIT, 1), 200)
    token = inst.access_token.strip()

    try:
        rows = tn_service.fetch_orders(
            tn_user_id,
            token,
            page=1,
            per_page=limit,
            aggregates="fulfillment_orders",
        )
    except httpx.TimeoutException:
        logger.warning("TN initial import: fetch_orders timeout store_id=%s", store_id)
        return
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        if code == 429:
            logger.warning("TN initial import: rate limited (429) store_id=%s", store_id)
        else:
            logger.error(
                "TN initial import: HTTP %s from TN store_id=%s",
                code,
                store_id,
            )
        return
    except httpx.RequestError as e:
        logger.warning(
            "TN initial import: request error store_id=%s: %s",
            store_id,
            e,
        )
        return
    except Exception:
        logger.exception("TN initial import: fetch_orders failed store_id=%s", store_id)
        return

    settings_for_region = db.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    phone_region = default_region_for_store(store, settings_for_region)

    created = 0
    for detail in rows:
        if not isinstance(detail, dict):
            continue
        try:
            with db.begin_nested():
                o = create_order_from_onboarding_detail(
                    db, store, detail, phone_region=phone_region
                )
                if o is not None:
                    created += 1
        except Exception:
            logger.exception(
                "TN initial import: single order failed store_id=%s detail_id=%s",
                store_id,
                detail.get("id"),
            )

    settings_row = db.query(StoreSettings).filter(StoreSettings.store_id == store_id).first()
    if not settings_row:
        settings_row = StoreSettings(store_id=store_id, onboarding_status="active")
        db.add(settings_row)
        db.flush()
    settings_row.tn_initial_import_completed_at = datetime.now(timezone.utc)
    db.commit()
    logger.info(
        "TN initial import done store_id=%s created=%s payload=%s",
        store_id,
        created,
        len(rows),
    )


def run_initial_orders_import_task(store_id: int) -> None:
    """Background task: own DB session (callback request session is closed)."""
    from backend.app.db.session import SessionLocal

    db = SessionLocal()
    try:
        run_initial_orders_import_in_session(db, store_id)
    finally:
        db.close()
