import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.models.store import Store, StoreSettings
from backend.app.models.order import Order
from backend.app.models.notification import NotificationAttempt


def _setup(session, **order_overrides):
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"Retry Store {uid}", external_store_id=f"tn_r_{uid}", status="active")
    session.add(store)
    session.flush()

    settings = StoreSettings(
        store_id=store.id,
        onboarding_status="active",
        weraha_enabled=True,
        whatsapp_enabled=True,
    )
    session.add(settings)

    defaults = dict(
        store_id=store.id,
        external_id=f"ord_r_{uid}",
        normalized_phone="+595981111111",
        tracking_number=f"WRH-R-{uid}",
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
def retry_session(engine):
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


class TestRetryAndIdempotency:
    def test_skip_second_attempt_on_permanent_graph_error(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        call_count = 0
        original_send = WhatsAppService.send_template_message

        def fail_permanent(self, **kwargs):
            nonlocal call_count
            call_count += 1
            return {
                "success": False,
                "error": "131047",
                "error_message": "Re-engagement message",
            }

        WhatsAppService.send_template_message = fail_permanent
        try:
            store, order = _setup(retry_session)
            engine = NotificationEngine(whatsapp=WhatsAppService(mock=False), max_retries=1)
            result = engine.evaluate_and_notify(retry_session, order)

            assert result["sent"] is False
            assert call_count == 1
        finally:
            WhatsAppService.send_template_message = original_send

    def test_retry_on_first_failure(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        call_count = 0
        original_send = WhatsAppService.send_template_message

        def fail_then_succeed(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": False, "error": "transient", "error_message": "Temporary failure"}
            return {"success": True, "message_id": "wamid.retry_ok"}

        WhatsAppService.send_template_message = fail_then_succeed
        try:
            store, order = _setup(retry_session)
            engine = NotificationEngine(whatsapp=WhatsAppService(mock=False), max_retries=1)
            result = engine.evaluate_and_notify(retry_session, order)

            assert result["sent"] is True
            assert result["attempt"] == 2
            assert call_count == 2
        finally:
            WhatsAppService.send_template_message = original_send

    def test_fail_after_retry(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup(retry_session)
        engine = NotificationEngine(
            whatsapp=WhatsAppService(mock=True, force_fail=True),
            max_retries=1,
        )

        result = engine.evaluate_and_notify(retry_session, order)
        assert result["sent"] is False
        assert result["reason"] == "send_failed"

        retry_session.refresh(order)
        assert order.notification_status == "failed"
        assert order.notification_error is not None

    def test_success_on_retry(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        call_count = 0
        original_send = WhatsAppService.send_template_message

        def fail_then_succeed(self, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"success": False, "error": "transient", "error_message": "Fail"}
            return {"success": True, "message_id": "wamid.retry_success"}

        WhatsAppService.send_template_message = fail_then_succeed
        try:
            store, order = _setup(retry_session)
            engine = NotificationEngine(whatsapp=WhatsAppService(mock=False), max_retries=1)
            result = engine.evaluate_and_notify(retry_session, order)

            retry_session.refresh(order)
            assert result["sent"] is True
            assert order.notification_status == "sent"
        finally:
            WhatsAppService.send_template_message = original_send

    def test_idempotency_prevents_duplicate(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup(retry_session)
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        r1 = engine.evaluate_and_notify(retry_session, order)
        assert r1["sent"] is True

        order.notified_in_transit = False
        retry_session.commit()

        r2 = engine.evaluate_and_notify(retry_session, order)
        assert r2["sent"] is False
        assert r2["reason"] == "already_notified"

    def test_retry_records_attempt_number(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup(retry_session)
        engine = NotificationEngine(
            whatsapp=WhatsAppService(mock=True, force_fail=True),
            max_retries=1,
        )

        engine.evaluate_and_notify(retry_session, order)

        attempts = (
            retry_session.query(NotificationAttempt)
            .filter(NotificationAttempt.order_id == order.id)
            .order_by(NotificationAttempt.attempt_number)
            .all()
        )
        assert len(attempts) == 2
        assert attempts[0].attempt_number == 1
        assert attempts[1].attempt_number == 2

    def test_notification_error_visible(self, retry_session):
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup(retry_session)
        engine = NotificationEngine(
            whatsapp=WhatsAppService(mock=True, force_fail=True),
            max_retries=1,
        )

        engine.evaluate_and_notify(retry_session, order)
        retry_session.refresh(order)

        assert order.notification_status == "failed"
        assert "Simulated" in order.notification_error

    def test_late_tracking_skips_in_transit(self, retry_session):
        """Order goes directly to delivered without ever being in_transit.
        Should send delivered notification only."""
        from backend.app.services.notification import NotificationEngine
        from backend.app.services.whatsapp import WhatsAppService

        store, order = _setup(
            retry_session,
            current_status="delivered",
            notified_in_transit=False,
            notified_delivered=False,
        )
        engine = NotificationEngine(whatsapp=WhatsAppService(mock=True))

        result = engine.evaluate_and_notify(retry_session, order)
        assert result["sent"] is True
        assert result["event_type"] == "delivered"
