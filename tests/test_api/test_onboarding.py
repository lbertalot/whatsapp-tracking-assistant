import uuid
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.app.core.security import create_access_token, create_tn_oauth_state, hash_password
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.store import Store, StoreInstallation, StoreSettings
from backend.app.models.user import StoreUser


@pytest.fixture
def onb_engine_client(engine):
    """Store + user listos para flujo OAuth con state (sin installation TN)."""
    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]
    store = Store(name="Onb Store", external_store_id=None, status="active")
    session.add(store)
    session.flush()
    session.add(StoreSettings(store_id=store.id, onboarding_status="pending"))
    user = StoreUser(
        store_id=store.id,
        email=f"onb_{uid}@test.com",
        password_hash=hash_password("Secret123!"),
    )
    session.add(user)
    session.commit()

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client, session, store, user

    app.dependency_overrides.clear()
    session.query(StoreUser).filter(StoreUser.store_id == store.id).delete()
    session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()
    session.close()


def test_onboarding_status_unauthenticated(client):
    r = client.get("/api/onboarding/status")
    assert r.status_code == 401


def test_onboarding_status_needs_tn(auth_env):
    from backend.app.core.security import create_access_token

    client, store, user, _email = auth_env
    token = create_access_token(user.id, store.id)
    r = client.get("/api/onboarding/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["needs_tiendanube"] is True
    assert data["installation_active"] is False
    assert data["oauth_callback_url"].endswith("/integrations/tiendanube/callback")
    assert data["webhook_public_url"].endswith("/webhooks/tiendanube")
    assert data["tiendanube_app_configured"] is True


def test_onboarding_status_linked(auth_env, engine):
    from backend.app.core.security import create_access_token

    client, store, user, _email = auth_env
    Session = sessionmaker(bind=engine)
    s = Session()
    s.add(
        StoreInstallation(
            store_id=store.id,
            order_source_type="tiendanube",
            access_token="tn-access-token-xyz",
            is_active=True,
        )
    )
    s.commit()
    s.close()

    token = create_access_token(user.id, store.id)
    r = client.get("/api/onboarding/status", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["needs_tiendanube"] is False
    assert data["installation_active"] is True
    assert "initial_orders_import_completed" in data
    assert data["initial_orders_import_completed"] is False


def test_tn_install_url_requires_auth(client):
    r = client.get("/api/integrations/tiendanube/install-url")
    assert r.status_code == 401


def test_tn_install_url_503_when_tn_not_configured(onb_engine_client, monkeypatch):
    from backend.app.core import config
    from backend.app.core.security import create_access_token

    monkeypatch.setattr(config.settings, "TIENDANUBE_APP_ID", "")
    monkeypatch.setattr(config.settings, "TIENDANUBE_CLIENT_SECRET", "")
    client, _session, store, user = onb_engine_client
    token = create_access_token(user.id, store.id)
    r = client.get(
        "/api/integrations/tiendanube/install-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 503
    assert "APP_ID" in r.json().get("detail", "") or "CLIENT_SECRET" in r.json().get("detail", "")


def test_tn_install_url_contains_state(onb_engine_client):
    client, _session, store, user = onb_engine_client
    token = create_access_token(user.id, store.id)
    r = client.get(
        "/api/integrations/tiendanube/install-url",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    url = r.json()["url"]
    assert "tiendanube.com" in url
    assert "state=" in url


def test_tn_callback_valid_state_links_store(onb_engine_client):
    from backend.app.api import integrations as integ_mod

    client, session, store, user = onb_engine_client
    state = create_tn_oauth_state(store.id)
    tn_uid = 88442211

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "tn-token-linked",
        "token_type": "bearer",
        "user_id": tn_uid,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        with patch.object(
            integ_mod.tn_service,
            "fetch_store_info",
            return_value={"name": {"es": "Mi Tienda Demo"}},
        ):
            with patch.object(integ_mod.tn_service, "register_webhooks", return_value=None):
                with patch(
                    "backend.app.services.tiendanube_initial_import.tn_service.fetch_orders",
                    return_value=[],
                ):
                    r = client.get(
                        f"/integrations/tiendanube/callback?code=auth-code-test&state={state}",
                        follow_redirects=False,
                    )

    assert r.status_code == 302
    assert "onboarding" in r.headers["location"]
    assert "success=1" in r.headers["location"]

    session.expire_all()
    st = session.query(Store).filter(Store.id == store.id).first()
    assert st.external_store_id == str(tn_uid)
    inst = session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).first()
    assert inst is not None
    assert inst.access_token == "tn-token-linked"
    assert inst.is_active is True
    sett = session.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    assert sett is not None
    assert sett.tn_initial_import_completed_at is not None


def test_tn_callback_invalid_state_redirect(onb_engine_client):
    client, session, store, user = onb_engine_client

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "x", "user_id": 1}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        r = client.get(
            "/integrations/tiendanube/callback?code=c&state=not-a-valid-jwt",
            follow_redirects=False,
        )

    assert r.status_code == 302
    assert "error=invalid_state" in r.headers["location"]


def test_tn_callback_store_conflict(onb_engine_client):
    client, session, store, user = onb_engine_client
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


def test_tn_callback_unknown_store_redirect(onb_engine_client):
    """state válido pero store_id inexistente → redirect a onboarding (no 404 JSON)."""
    client, session, store, user = onb_engine_client
    ghost_id = 9_999_999_999
    state = create_tn_oauth_state(ghost_id)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"access_token": "x", "user_id": 1}
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        r = client.get(
            f"/integrations/tiendanube/callback?code=c&state={state}",
            follow_redirects=False,
        )

    assert r.status_code == 302
    assert "error=unknown_store" in r.headers["location"]


def test_reimport_orders_requires_auth(client):
    r = client.post("/api/integrations/tiendanube/reimport-orders")
    assert r.status_code == 401


def test_reimport_orders_400_without_tiendanube(onb_engine_client):
    client, _session, store, user = onb_engine_client
    token = create_access_token(user.id, store.id)
    r = client.post(
        "/api/integrations/tiendanube/reimport-orders",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "tiendanube" in r.json()["detail"].lower()


def test_reimport_orders_success_resets_timestamp_and_schedules_task(onb_engine_client):
    client, session, store, user = onb_engine_client
    store.external_store_id = "887766"
    session.add(
        StoreInstallation(
            store_id=store.id,
            order_source_type="tiendanube",
            access_token="tok-reimport",
            is_active=True,
        )
    )
    ss = session.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    ss.tn_initial_import_completed_at = datetime.utcnow()
    session.commit()

    token = create_access_token(user.id, store.id)
    with patch("backend.app.api.integrations.run_initial_orders_import_task") as m:
        r = client.post(
            "/api/integrations/tiendanube/reimport-orders",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"
    m.assert_called_once_with(store.id)
    session.expire_all()
    ss2 = session.query(StoreSettings).filter(StoreSettings.store_id == store.id).first()
    assert ss2.tn_initial_import_completed_at is None


def test_exchange_code_sends_json():
    from backend.app.services.tiendanube import TiendanubeService

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"access_token": "a", "user_id": 1}

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response) as m:
        svc = TiendanubeService()
        svc.exchange_code("my-code")

    assert m.called
    kwargs = m.call_args.kwargs
    assert "json" in kwargs
    assert kwargs["json"]["grant_type"] == "authorization_code"
    assert kwargs["json"]["code"] == "my-code"
    assert kwargs["headers"].get("Content-Type") == "application/json"
