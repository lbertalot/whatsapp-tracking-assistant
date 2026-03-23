"""
E2E lógico: seed oauth_ready + onboarding status + callback TN (mock).
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.skip(
    reason="Requiere MS-ONB01 (routers /api/onboarding, callback TN) no incluidos en esta rama"
)

from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import backend.app.db.session as db_session_mod
from backend.app.core.security import create_access_token, create_tn_oauth_state
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.notification import NotificationAttempt
from backend.app.models.order import Order
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser


def _delete_store_cascade(session, store_id: int) -> None:
    order_ids = [r[0] for r in session.query(Order.id).filter(Order.store_id == store_id).all()]
    if order_ids:
        session.query(NotificationAttempt).filter(
            NotificationAttempt.order_id.in_(order_ids)
        ).delete(synchronize_session=False)
        session.query(Order).filter(Order.store_id == store_id).delete(synchronize_session=False)
    session.query(StoreUser).filter(StoreUser.store_id == store_id).delete(
        synchronize_session=False
    )
    session.query(StoreSettings).filter(StoreSettings.store_id == store_id).delete(
        synchronize_session=False
    )
    session.query(StoreInstallation).filter(StoreInstallation.store_id == store_id).delete(
        synchronize_session=False
    )
    session.query(Store).filter(Store.id == store_id).delete(synchronize_session=False)
    session.commit()


@pytest.fixture
def seed_oauth_engine_client(engine, monkeypatch):
    """Corre seed en modo oauth_ready con email único; comparte engine con TestClient."""
    uid = uuid.uuid4().hex[:8]
    email = f"seed_oauth_{uid}@test.com"
    monkeypatch.setenv("SEED_TN_LINK_MODE", "oauth_ready")
    monkeypatch.setenv("SEED_USER_EMAIL", email)
    monkeypatch.setenv("SEED_USER_PASSWORD", "SeedOAuthTest123!")

    # `seed()` usa SessionLocal global; alinearlo al engine de pytest (mismas tablas).
    monkeypatch.setattr(db_session_mod, "engine", engine)
    monkeypatch.setattr(
        db_session_mod,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=engine),
    )

    from scripts import seed_demo_data

    seed_demo_data.seed()

    Session = sessionmaker(bind=engine)
    session = Session()
    user = session.query(StoreUser).filter(StoreUser.email == email).first()
    assert user is not None
    store = session.query(Store).filter(Store.id == user.store_id).first()
    assert store is not None
    assert store.external_store_id is None

    inst = (
        session.query(StoreInstallation)
        .filter(
            StoreInstallation.store_id == store.id,
            StoreInstallation.order_source_type == "tiendanube",
        )
        .first()
    )
    assert inst is not None
    assert not (inst.access_token or "").strip()
    assert inst.is_active is False

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client, session, store, user, email

    app.dependency_overrides.clear()
    _delete_store_cascade(session, store.id)
    session.close()


def test_seed_oauth_ready_needs_tiendanube(seed_oauth_engine_client):
    client, session, store, user, _email = seed_oauth_engine_client
    token = create_access_token(user.id, store.id)
    r = client.get("/api/onboarding/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["needs_tiendanube"] is True
    assert data["installation_active"] is False
    assert data["tiendanube_user_id"] is None


def test_seed_oauth_ready_callback_links_real_tn_user(seed_oauth_engine_client):
    from backend.app.api import integrations as integ_mod

    client, session, store, user, _email = seed_oauth_engine_client
    state = create_tn_oauth_state(store.id)
    tn_uid = 99112233

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "real-tn-token",
        "token_type": "bearer",
        "user_id": tn_uid,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        with patch.object(
            integ_mod.tn_service,
            "fetch_store_info",
            return_value={"name": "Berta Shop"},
        ):
            with patch.object(integ_mod.tn_service, "register_webhooks", return_value=None):
                r = client.get(
                    f"/integrations/tiendanube/callback?code=seed-oauth-code&state={state}",
                    follow_redirects=False,
                )

    assert r.status_code == 302
    assert "success=1" in r.headers["location"]
    assert "store_conflict" not in r.headers["location"]

    session.expire_all()
    st = session.query(Store).filter(Store.id == store.id).first()
    assert st.external_store_id == str(tn_uid)
    inst = session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).first()
    assert inst.access_token == "real-tn-token"
    assert inst.is_active is True

    token = create_access_token(user.id, store.id)
    r2 = client.get("/api/onboarding/status", headers={"Authorization": f"Bearer {token}"})
    assert r2.json()["needs_tiendanube"] is False


def test_seed_oauth_ready_store_conflict_if_external_mismatch(seed_oauth_engine_client):
    """Regresión: external_store_id previo distinto al user_id TN → store_conflict."""
    client, session, store, user, _email = seed_oauth_engine_client
    store.external_store_id = "111"
    session.commit()

    state = create_tn_oauth_state(store.id)
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "x", "user_id": 222}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        r = client.get(
            f"/integrations/tiendanube/callback?code=c&state={state}",
            follow_redirects=False,
        )

    assert r.status_code == 302
    assert "error=store_conflict" in r.headers["location"]


def test_seed_demo_mode_panel_skip_onboarding(engine, monkeypatch):
    """Modo demo: token placeholder → no necesita TN en status."""
    uid = uuid.uuid4().hex[:8]
    email = f"seed_demo_{uid}@test.com"
    monkeypatch.setenv("SEED_TN_LINK_MODE", "demo")
    monkeypatch.setenv("SEED_USER_EMAIL", email)
    monkeypatch.setenv("SEED_USER_PASSWORD", "DemoMode123!")
    monkeypatch.setenv("SEED_STORE_EXTERNAL_ID", f"demo-ext-{uid}")

    monkeypatch.setattr(db_session_mod, "engine", engine)
    monkeypatch.setattr(
        db_session_mod,
        "SessionLocal",
        sessionmaker(autocommit=False, autoflush=False, bind=engine),
    )

    from scripts import seed_demo_data

    seed_demo_data.seed()

    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        user = session.query(StoreUser).filter(StoreUser.email == email).first()
        store = session.query(Store).filter(Store.id == user.store_id).first()
        token = create_access_token(user.id, store.id)

        def _override():
            s = Session()
            try:
                yield s
            finally:
                s.close()

        app.dependency_overrides[get_db] = _override
        client = TestClient(app)
        r = client.get("/api/onboarding/status", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["needs_tiendanube"] is False
        app.dependency_overrides.clear()

        _delete_store_cascade(session, store.id)
    finally:
        session.close()
