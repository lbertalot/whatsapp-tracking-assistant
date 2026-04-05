"""MS-ONB03: initial Tiendanube orders import."""

import uuid
from unittest.mock import patch

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser
from backend.app.services.tiendanube_initial_import import (
    create_order_from_onboarding_detail,
    run_initial_orders_import_in_session,
)


@pytest.fixture
def import_store(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    uid = uuid.uuid4().hex[:8]
    store = Store(
        name="Import Store", external_store_id=str(555001 + hash(uid) % 10000), status="active"
    )
    session.add(store)
    session.flush()
    session.add(StoreSettings(store_id=store.id, onboarding_status="active"))
    session.add(
        StoreInstallation(
            store_id=store.id,
            order_source_type="tiendanube",
            access_token="tok-import",
            is_active=True,
        )
    )
    session.commit()
    yield session, store
    session.query(Order).filter(Order.store_id == store.id).delete()
    session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    session.query(StoreUser).filter(StoreUser.store_id == store.id).delete()
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()
    session.close()


def test_create_order_from_detail_skips_duplicate(import_store):
    session, store = import_store
    detail = {
        "id": 9001,
        "contact_phone": "+595981111111",
        "contact_name": "Test Buyer",
        "shipping_status": "unpacked",
        "status": "open",
    }
    o1 = create_order_from_onboarding_detail(session, store, detail)
    assert o1 is not None
    assert o1.external_id == "9001"
    assert o1.notified_in_transit is True
    assert o1.notified_delivered is True
    assert o1.last_status_source == "onboarding_import"

    o2 = create_order_from_onboarding_detail(session, store, detail)
    assert o2 is None


def test_run_initial_import_creates_orders_and_marks_completed(import_store):
    session, store = import_store
    payload = [
        {
            "id": 9101,
            "contact_phone": "+595982222222",
            "contact_name": "A",
            "shipping_status": "delivered",
            "status": "closed",
        },
        {
            "id": 9102,
            "contact_phone": "+595983333333",
            "contact_name": "B",
            "shipping_status": "unpacked",
            "status": "open",
        },
    ]
    with patch(
        "backend.app.services.tiendanube_initial_import.tn_service.fetch_orders",
        return_value=payload,
    ):
        run_initial_orders_import_in_session(session, store.id)

    session.expire_all()
    rows = session.query(Order).filter(Order.store_id == store.id).all()
    assert len(rows) == 2
    st = session.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    assert st.tn_initial_import_completed_at is not None


def test_run_initial_import_skips_when_already_completed(import_store):
    session, store = import_store
    st = session.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    from datetime import datetime

    st.tn_initial_import_completed_at = datetime.utcnow()
    session.commit()

    with patch(
        "backend.app.services.tiendanube_initial_import.tn_service.fetch_orders",
        return_value=[{"id": 9200, "status": "open"}],
    ) as m:
        run_initial_orders_import_in_session(session, store.id)

    m.assert_not_called()


def test_run_initial_import_fetch_orders_http_error_does_not_complete(import_store):
    session, store = import_store
    req = httpx.Request("GET", "https://api.tiendanube.com/v1/1/orders")
    resp = httpx.Response(503, request=req)
    exc = httpx.HTTPStatusError("srv err", request=req, response=resp)
    with patch(
        "backend.app.services.tiendanube_initial_import.tn_service.fetch_orders",
        side_effect=exc,
    ):
        run_initial_orders_import_in_session(session, store.id)

    session.expire_all()
    st = session.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    assert st.tn_initial_import_completed_at is None
