import uuid

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app.core.config import settings
from backend.app.models.store import Store, StoreSettings
from backend.app.services.whatsapp import WhatsAppService


@pytest.fixture
def resolve_session(engine):
    Session = sessionmaker(bind=engine)
    s = Session()
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"WA resolve {uid}", external_store_id=f"tn-{uid}", status="active")
    s.add(store)
    s.flush()
    st = StoreSettings(
        store_id=store.id,
        onboarding_status="active",
        whatsapp_phone_number_id="111",
        whatsapp_access_token="STORE_TOKEN",
        whatsapp_template_language="es_AR",
    )
    s.add(st)
    s.commit()
    yield s, store.id
    s.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    s.query(Store).filter(Store.id == store.id).delete()
    s.commit()
    s.close()


def test_resolve_uses_store_credentials(resolve_session, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ALLOW_GLOBAL_FALLBACK", True)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "GLOBAL_TOKEN")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "999")
    session, store_id = resolve_session

    wa = WhatsAppService.resolve_for_store(session, store_id)
    assert wa.mock is False
    assert wa.access_token == "STORE_TOKEN"
    assert wa.phone_number_id == "111"
    assert wa.template_language == "es_AR"


def test_resolve_global_fallback_when_store_missing_token(engine, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ALLOW_GLOBAL_FALLBACK", True)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "GLOBAL_ONLY")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "888")
    Session = sessionmaker(bind=engine)
    s = Session()
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"WA fb {uid}", external_store_id=f"tn-{uid}", status="active")
    s.add(store)
    s.flush()
    s.add(
        StoreSettings(
            store_id=store.id,
            onboarding_status="active",
            whatsapp_phone_number_id="",
            whatsapp_access_token=None,
        )
    )
    s.commit()

    wa = WhatsAppService.resolve_for_store(s, store.id)
    assert wa.mock is False
    assert wa.access_token == "GLOBAL_ONLY"
    assert wa.phone_number_id == "888"

    s.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    s.query(Store).filter(Store.id == store.id).delete()
    s.commit()
    s.close()


def test_resolve_no_fallback_returns_empty_creds(engine, monkeypatch):
    monkeypatch.setattr(settings, "WHATSAPP_ALLOW_GLOBAL_FALLBACK", False)
    monkeypatch.setattr(settings, "WHATSAPP_ACCESS_TOKEN", "SHOULD_NOT_USE")
    monkeypatch.setattr(settings, "WHATSAPP_PHONE_NUMBER_ID", "999")
    monkeypatch.setattr(settings, "APP_ENV", "production")
    Session = sessionmaker(bind=engine)
    s = Session()
    uid = uuid.uuid4().hex[:8]
    store = Store(name=f"WA prod {uid}", external_store_id=f"tn-{uid}", status="active")
    s.add(store)
    s.flush()
    s.add(StoreSettings(store_id=store.id, onboarding_status="active"))
    s.commit()

    wa = WhatsAppService.resolve_for_store(s, store.id)
    assert wa.mock is False
    assert wa.access_token == ""
    assert wa.phone_number_id == ""

    s.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    s.query(Store).filter(Store.id == store.id).delete()
    s.commit()
    s.close()

    monkeypatch.setattr(settings, "APP_ENV", "testing")
