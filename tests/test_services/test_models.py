import pytest
from sqlalchemy.exc import IntegrityError


def _make_store(db_session, **overrides):
    from backend.app.models.store import Store
    data = {"name": "Test Store", "external_store_id": "tn_100", **overrides}
    store = Store(**data)
    db_session.add(store)
    db_session.flush()
    return store


def _make_user(db_session, store, **overrides):
    from backend.app.models.user import StoreUser
    data = {
        "store_id": store.id,
        "email": "merchant@test.com",
        "password_hash": "hashed_pw",
        **overrides,
    }
    user = StoreUser(**data)
    db_session.add(user)
    db_session.flush()
    return user


def _make_order(db_session, store, **overrides):
    from backend.app.models.order import Order
    data = {
        "store_id": store.id,
        "external_id": "order_1",
        "normalized_phone": "+595981000000",
        **overrides,
    }
    order = Order(**data)
    db_session.add(order)
    db_session.flush()
    return order


class TestStoreModel:
    def test_store_create(self, db_session):
        store = _make_store(db_session)
        assert store.id is not None
        assert store.name == "Test Store"
        assert store.country == "Paraguay"
        assert store.status == "pending"

    def test_store_external_id_unique(self, db_session):
        _make_store(db_session, external_store_id="tn_dup")
        with pytest.raises(IntegrityError):
            _make_store(db_session, external_store_id="tn_dup")
        db_session.rollback()


class TestStoreSettingsModel:
    def test_store_settings_create(self, db_session):
        from backend.app.models.store import StoreSettings
        store = _make_store(db_session, external_store_id="tn_settings")
        settings = StoreSettings(store_id=store.id)
        db_session.add(settings)
        db_session.flush()
        assert settings.onboarding_status == "pending"
        assert settings.weraha_enabled is False
        assert settings.whatsapp_enabled is False

    def test_store_settings_unique_per_store(self, db_session):
        from backend.app.models.store import StoreSettings
        store = _make_store(db_session, external_store_id="tn_set_uniq")
        db_session.add(StoreSettings(store_id=store.id))
        db_session.flush()
        with pytest.raises(IntegrityError):
            db_session.add(StoreSettings(store_id=store.id))
            db_session.flush()
        db_session.rollback()


class TestStoreUserModel:
    def test_store_user_email_unique(self, db_session):
        s1 = _make_store(db_session, external_store_id="tn_u1")
        s2 = _make_store(db_session, external_store_id="tn_u2")
        _make_user(db_session, s1, email="dup@test.com")
        with pytest.raises(IntegrityError):
            _make_user(db_session, s2, email="dup@test.com")
        db_session.rollback()


class TestOrderModel:
    def test_order_belongs_to_store(self, db_session):
        store = _make_store(db_session, external_store_id="tn_ord")
        order = _make_order(db_session, store)
        assert order.store_id == store.id

    def test_order_requires_store(self, db_session):
        from backend.app.models.order import Order
        from sqlalchemy import inspect
        mapper = inspect(Order)
        store_id_col = mapper.columns["store_id"]
        assert store_id_col.nullable is False
        fks = list(store_id_col.foreign_keys)
        assert len(fks) == 1
        assert "stores.id" in str(fks[0])

    def test_order_default_values(self, db_session):
        store = _make_store(db_session, external_store_id="tn_def")
        order = _make_order(db_session, store, external_id="def_order")
        assert order.notified_in_transit is False
        assert order.notified_delivered is False
        assert order.invalid_phone is False
        assert order.notification_status is None


class TestNotificationAttemptModel:
    def test_notification_attempt_create(self, db_session):
        from backend.app.models.notification import NotificationAttempt
        store = _make_store(db_session, external_store_id="tn_notif")
        order = _make_order(db_session, store, external_id="notif_order")
        attempt = NotificationAttempt(
            store_id=store.id,
            order_id=order.id,
            event_type="in_transit",
            idempotency_key=f"{store.id}:{order.id}:in_transit",
            status="sent",
            template_name="shipping_in_transit_v1",
        )
        db_session.add(attempt)
        db_session.flush()
        assert attempt.id is not None
        assert attempt.attempt_number == 1

    def test_notification_attempt_idempotency_key_unique(self, db_session):
        from backend.app.models.notification import NotificationAttempt
        store = _make_store(db_session, external_store_id="tn_idem")
        order = _make_order(db_session, store, external_id="idem_order")
        key = f"{store.id}:{order.id}:delivered"
        db_session.add(NotificationAttempt(
            store_id=store.id, order_id=order.id,
            event_type="delivered", idempotency_key=key, status="sent",
        ))
        db_session.flush()
        with pytest.raises(IntegrityError):
            db_session.add(NotificationAttempt(
                store_id=store.id, order_id=order.id,
                event_type="delivered", idempotency_key=key, status="sent",
            ))
            db_session.flush()
        db_session.rollback()
