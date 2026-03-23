import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.models.order import Order
from backend.app.models.store import Store, StoreSettings


@pytest.fixture
def worker_data(engine):
    """Creates stores and orders for worker tests."""
    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]

    active_store = Store(name="Active Store", external_store_id=f"tn_w_{uid}", status="active")
    inactive_store = Store(
        name="Inactive Store", external_store_id=f"tn_wi_{uid}", status="pending"
    )
    session.add_all([active_store, inactive_store])
    session.flush()

    active_settings = StoreSettings(
        store_id=active_store.id,
        onboarding_status="active",
        weraha_enabled=True,
    )
    session.add(active_settings)
    session.flush()

    eligible = Order(
        store_id=active_store.id,
        external_id=f"elig_{uid}",
        normalized_phone="+595981111111",
        tracking_number="WRH-ELIG",
        current_status="pending_tracking",
    )
    no_tracking = Order(
        store_id=active_store.id,
        external_id=f"notrack_{uid}",
        normalized_phone="+595982222222",
        tracking_number=None,
        current_status="pending_tracking",
    )
    inactive_order = Order(
        store_id=inactive_store.id,
        external_id=f"inact_{uid}",
        normalized_phone="+595983333333",
        tracking_number="WRH-INACT",
        current_status="pending_tracking",
    )
    already_delivered = Order(
        store_id=active_store.id,
        external_id=f"deliv_{uid}",
        normalized_phone="+595984444444",
        tracking_number="WRH-DELIV",
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
    assert no_tracking.id not in order_ids
    assert inactive_order.id not in order_ids
    assert already_delivered.id not in order_ids


def test_worker_updates_order_status(worker_data):
    session, active_store, _, eligible, *_ = worker_data
    from backend.app.workers.polling import process_order

    with patch("backend.app.workers.polling.weraha_adapter") as mock_weraha:
        mock_weraha.get_tracking_status.return_value = {
            "tracking_number": "WRH-ELIG",
            "status": "EN_CAMINO",
        }
        process_order(session, eligible)

    session.refresh(eligible)
    assert eligible.current_status == "in_transit"


def test_worker_skips_inactive_store(worker_data):
    session, _, inactive_store, _, _, inactive_order, _ = worker_data
    from backend.app.workers.polling import get_eligible_orders

    orders = get_eligible_orders(session)
    assert inactive_order.id not in [o.id for o in orders]


def test_worker_skips_no_tracking(worker_data):
    session, *_ = worker_data
    from backend.app.workers.polling import get_eligible_orders

    orders = get_eligible_orders(session)
    assert all(o.tracking_number is not None for o in orders)


def test_worker_updates_last_checked(worker_data):
    session, _, _, eligible, *_ = worker_data
    from backend.app.workers.polling import process_order

    before = eligible.last_checked_at

    with patch("backend.app.workers.polling.weraha_adapter") as mock_weraha:
        mock_weraha.get_tracking_status.return_value = {
            "tracking_number": "WRH-ELIG",
            "status": "EN_CAMINO",
        }
        process_order(session, eligible)

    session.refresh(eligible)
    assert eligible.last_checked_at is not None
    assert eligible.last_checked_at != before
