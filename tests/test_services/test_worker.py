import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings


@pytest.fixture
def worker_data(engine):
    """Creates stores, TN installation, and orders for worker sync tests."""
    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]
    tn_uid = str(9_000_000 + (int(uid[:6], 16) % 999_999))
    tn_uid_inactive = str(8_000_000 + (int(uid[6:], 16) % 999_999))

    active_store = Store(name="Active Store", external_store_id=tn_uid, status="active")
    inactive_store = Store(
        name="Inactive Store", external_store_id=tn_uid_inactive, status="pending"
    )
    session.add_all([active_store, inactive_store])
    session.flush()

    session.add(
        StoreInstallation(
            store_id=active_store.id,
            order_source_type="tiendanube",
            access_token="fake-tn-token",
            is_active=True,
        )
    )

    active_settings = StoreSettings(
        store_id=active_store.id,
        onboarding_status="active",
        ecommerce_sync_enabled=True,
    )
    session.add(active_settings)
    session.flush()

    # Numeric TN order ids for int(external_id) in worker
    oid_base = 7000000 + (int(uid[:6], 16) % 100000)
    eligible = Order(
        store_id=active_store.id,
        external_id=str(oid_base + 1),
        normalized_phone="+595981111111",
        tracking_number="TRK-ELIG",
        current_status="pending_tracking",
    )
    no_tracking = Order(
        store_id=active_store.id,
        external_id=str(oid_base + 2),
        normalized_phone="+595982222222",
        tracking_number=None,
        current_status="pending_tracking",
    )
    inactive_order = Order(
        store_id=inactive_store.id,
        external_id=str(oid_base + 3),
        normalized_phone="+595983333333",
        tracking_number="TRK-INACT",
        current_status="pending_tracking",
    )
    already_delivered = Order(
        store_id=active_store.id,
        external_id=str(oid_base + 4),
        normalized_phone="+595984444444",
        tracking_number="TRK-DELIV",
        current_status="delivered",
    )
    session.add_all([eligible, no_tracking, inactive_order, already_delivered])
    session.commit()

    yield (
        session,
        active_store,
        inactive_store,
        eligible,
        no_tracking,
        inactive_order,
        already_delivered,
    )

    from backend.app.models.notification import NotificationAttempt

    session.query(NotificationAttempt).filter(
        NotificationAttempt.store_id.in_([active_store.id, inactive_store.id])
    ).delete(synchronize_session=False)
    session.query(Order).filter(Order.store_id.in_([active_store.id, inactive_store.id])).delete(
        synchronize_session=False
    )
    session.query(StoreInstallation).filter(StoreInstallation.store_id == active_store.id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == active_store.id).delete()
    session.query(Store).filter(Store.id.in_([active_store.id, inactive_store.id])).delete(
        synchronize_session=False
    )
    session.commit()
    session.close()


def test_worker_selects_eligible_orders(worker_data):
    (
        session,
        active_store,
        inactive_store,
        eligible,
        no_tracking,
        inactive_order,
        already_delivered,
    ) = worker_data
    from backend.app.workers.polling import get_eligible_orders

    orders = get_eligible_orders(session)
    order_ids = [o.id for o in orders]

    assert eligible.id in order_ids
    assert no_tracking.id in order_ids
    assert inactive_order.id not in order_ids
    assert already_delivered.id not in order_ids


def test_worker_updates_order_status_from_tn_detail(worker_data):
    session, _, _, eligible, *_ = worker_data
    from backend.app.workers.polling import process_order

    detail = {
        "id": int(eligible.external_id),
        "shipping_status": "shipped",
        "fulfillment_orders": [{"tracking_info": {"code": "TRK-ELIG", "url": "https://x.test"}}],
    }

    with patch("backend.app.workers.polling.tn_service.fetch_order", return_value=detail):
        process_order(session, eligible)

    session.refresh(eligible)
    assert eligible.current_status == "in_transit"


def test_worker_skips_inactive_store(worker_data):
    session, _, inactive_store, _, _, inactive_order, _ = worker_data
    from backend.app.workers.polling import get_eligible_orders

    orders = get_eligible_orders(session)
    assert inactive_order.id not in [o.id for o in orders]


def test_worker_excludes_store_when_ecommerce_sync_disabled(worker_data):
    session, active_store, _, eligible, *_ = worker_data
    from backend.app.workers.polling import get_eligible_orders

    st = session.query(StoreSettings).filter_by(store_id=active_store.id).first()
    st.ecommerce_sync_enabled = False
    session.commit()

    orders = get_eligible_orders(session)
    assert eligible.id not in [o.id for o in orders]


def test_worker_updates_last_checked(worker_data):
    session, _, _, eligible, *_ = worker_data
    from backend.app.workers.polling import process_order

    detail = {
        "id": int(eligible.external_id),
        "shipping_status": "delivered",
        "fulfillment_orders": [],
    }

    with patch("backend.app.workers.polling.tn_service.fetch_order", return_value=detail):
        process_order(session, eligible)

    session.refresh(eligible)
    assert eligible.last_checked_at is not None
