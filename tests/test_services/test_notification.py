import uuid
from unittest.mock import patch

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.models.store import Store, StoreSettings
from backend.app.models.order import Order
from backend.app.models.notification import NotificationAttempt


def _setup_store_and_order(session, **order_overrides):
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"Notif Store {uid}", external_store_id=f"tn_n_{uid}", status="active")
    session.add(store)
    session.flush()

    settings = StoreSettings(store_id=store.id, onboarding_status="active", weraha_enabled=True)
    session.add(settings)

    defaults = dict(
        store_id=store.id,
        external_id=f"ord_{uid}",
        normalized_phone="+595981111111",
        tracking_number=f"WRH-{uid}",
        current_status="in_transit",
        invalid_phone=False,
        notified_in_transit=False,
        notified_delivered=False,
    )
    defaults.update(order_overrides)
    order = Order(**defaults)
    session.add(order)
    session.commit()
    return store, order


@pytest.fixture
def notif_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestNotificationEngine:
    def test_sends_in_transit(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(notif_session, current_status="in_transit")
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        result = engine.evaluate_and_notify(notif_session, order)
        assert result["sent"] is True
        assert result["event_type"] == "in_transit"

    def test_sends_delivered(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(
            notif_session, current_status="delivered", notified_in_transit=True
        )
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        result = engine.evaluate_and_notify(notif_session, order)
        assert result["sent"] is True
        assert result["event_type"] == "delivered"

    def test_skips_already_notified(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(
            notif_session, current_status="in_transit", notified_in_transit=True
        )
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        result = engine.evaluate_and_notify(notif_session, order)
        assert result["sent"] is False
        assert result["reason"] == "already_notified"

    def test_records_attempt(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(notif_session, current_status="in_transit")
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        engine.evaluate_and_notify(notif_session, order)

        attempts = (
            notif_session.query(NotificationAttempt)
            .filter(NotificationAttempt.order_id == order.id)
            .all()
        )
        assert len(attempts) >= 1
        assert attempts[0].event_type == "in_transit"
        assert attempts[0].status == "sent"

    def test_updates_order_visibility(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(notif_session, current_status="in_transit")
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        engine.evaluate_and_notify(notif_session, order)
        notif_session.refresh(order)

        assert order.last_message_type == "in_transit"
        assert order.last_template_name is not None
        assert order.notification_status == "sent"
        assert order.last_notification_at is not None

    def test_sets_first_notification_at_once(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(notif_session, current_status="in_transit")
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        engine.evaluate_and_notify(notif_session, order)
        notif_session.refresh(order)
        first = order.first_notification_at
        assert first is not None

        order.current_status = "delivered"
        order.notified_in_transit = True
        order.notified_delivered = False
        notif_session.commit()

        engine.evaluate_and_notify(notif_session, order)
        notif_session.refresh(order)
        assert order.first_notification_at == first

    def test_invalid_phone_skips(self, notif_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup_store_and_order(
            notif_session, current_status="in_transit", invalid_phone=True
        )
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        result = engine.evaluate_and_notify(notif_session, order)
        assert result["sent"] is False
        assert result["reason"] == "invalid_phone"
