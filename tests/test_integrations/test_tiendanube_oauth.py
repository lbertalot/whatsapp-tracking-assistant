import uuid
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.store import Store, StoreInstallation


@pytest.fixture
def tn_env(engine):
    Session = sessionmaker(bind=engine)
    session = Session()

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client, session

    app.dependency_overrides.clear()
    session.rollback()
    session.close()


def test_install_redirects_to_tn(tn_env):
    client, _ = tn_env
    response = client.get("/integrations/tiendanube/install", follow_redirects=False)
    assert response.status_code in (302, 307)
    location = response.headers["location"]
    assert "tiendanube.com" in location
    assert "authorize" in location


def test_callback_exchanges_code(tn_env):
    client, session = tn_env

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "fake-tn-access-token",
        "token_type": "bearer",
        "scope": "write_orders read_orders",
        "user_id": 12345,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        response = client.get(
            "/integrations/tiendanube/callback?code=test-auth-code",
            follow_redirects=False,
        )

    assert response.status_code in (200, 302)


def test_callback_invalid_code(tn_env):
    client, _ = tn_env

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.raise_for_status.side_effect = Exception("Bad request")
    mock_response.text = "invalid code"

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        response = client.get(
            "/integrations/tiendanube/callback?code=bad-code",
            follow_redirects=False,
        )

    assert response.status_code in (400, 401, 422)


def test_callback_creates_store(tn_env):
    client, session = tn_env
    uid = uuid.uuid4().hex[:8]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": f"tok-{uid}",
        "token_type": "bearer",
        "scope": "write_orders",
        "user_id": int(uid[:6], 16),
    }
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        client.get(f"/integrations/tiendanube/callback?code=code-{uid}", follow_redirects=False)

    tn_user_id = str(int(uid[:6], 16))
    store = session.query(Store).filter(Store.external_store_id == tn_user_id).first()
    assert store is not None
    assert store.status in ("active", "pending")

    inst = session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).first()
    assert inst is not None
    assert inst.access_token == f"tok-{uid}"
    assert inst.is_active is True

    from backend.app.models.store import StoreSettings
    session.query(StoreInstallation).filter(StoreInstallation.store_id == store.id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == store.id).delete()
    session.query(Store).filter(Store.id == store.id).delete()
    session.commit()


def test_callback_idempotent(tn_env):
    client, session = tn_env
    user_id = 99999

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "tok-first",
        "token_type": "bearer",
        "scope": "write_orders",
        "user_id": user_id,
    }
    mock_response.raise_for_status = MagicMock()

    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        client.get("/integrations/tiendanube/callback?code=code1", follow_redirects=False)

    mock_response.json.return_value["access_token"] = "tok-second"
    with patch("backend.app.services.tiendanube.httpx.post", return_value=mock_response):
        client.get("/integrations/tiendanube/callback?code=code2", follow_redirects=False)

    stores = session.query(Store).filter(Store.external_store_id == str(user_id)).all()
    assert len(stores) == 1

    inst = (
        session.query(StoreInstallation)
        .filter(StoreInstallation.store_id == stores[0].id)
        .first()
    )
    assert inst.access_token == "tok-second"

    from backend.app.models.store import StoreSettings
    session.query(StoreInstallation).filter(StoreInstallation.store_id == stores[0].id).delete()
    session.query(StoreSettings).filter(StoreSettings.store_id == stores[0].id).delete()
    session.query(Store).filter(Store.id == stores[0].id).delete()
    session.commit()
