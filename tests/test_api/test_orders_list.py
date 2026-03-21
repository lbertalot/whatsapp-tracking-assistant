import uuid

import pytest
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.app.core.security import hash_password, create_access_token
from backend.app.db.session import get_db
from backend.app.main import app
from backend.app.models.store import Store
from backend.app.models.user import StoreUser
from backend.app.models.order import Order


@pytest.fixture
def orders_env(engine):
    """Two stores with orders — tests must verify isolation."""
    Session = sessionmaker(bind=engine)
    session = Session()

    uid = uuid.uuid4().hex[:8]

    store_a = Store(name="Store A", external_store_id=f"tn_a_{uid}", status="active")
    store_b = Store(name="Store B", external_store_id=f"tn_b_{uid}", status="active")
    session.add_all([store_a, store_b])
    session.flush()

    user_a = StoreUser(
        store_id=store_a.id,
        email=f"user_a_{uid}@test.com",
        password_hash=hash_password("pass"),
    )
    session.add(user_a)
    session.flush()

    orders_a = []
    for i in range(5):
        o = Order(
            store_id=store_a.id,
            external_id=f"ord_a_{uid}_{i}",
            normalized_phone="+595981000001",
            current_status="in_transit" if i < 3 else "delivered",
            notification_status="sent" if i < 2 else "pending",
            tracking_number=f"WRH-{uid}-{i}",
            last_message_type="in_transit" if i < 2 else None,
            last_template_name="shipping_in_transit_v1" if i < 2 else None,
        )
        orders_a.append(o)

    order_b = Order(
        store_id=store_b.id,
        external_id=f"ord_b_{uid}_0",
        normalized_phone="+595982000001",
        current_status="in_transit",
        tracking_number=f"WRH-B-{uid}",
    )
    session.add_all(orders_a + [order_b])
    session.commit()

    token_a = create_access_token(user_id=user_a.id, store_id=store_a.id)

    def _override():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _override
    client = TestClient(app)

    yield client, token_a, store_a, store_b, orders_a

    app.dependency_overrides.clear()
    session.query(Order).filter(Order.store_id.in_([store_a.id, store_b.id])).delete(synchronize_session=False)
    session.query(StoreUser).filter(StoreUser.id == user_a.id).delete()
    session.query(Store).filter(Store.id.in_([store_a.id, store_b.id])).delete(synchronize_session=False)
    session.commit()
    session.close()


def _auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_get_orders_requires_auth(orders_env):
    client, *_ = orders_env
    response = client.get("/orders")
    assert response.status_code == 401


def test_get_orders_scoped_by_store(orders_env):
    client, token, store_a, store_b, orders_a = orders_env
    response = client.get("/orders", headers=_auth_headers(token))
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) == 5
    for item in data["items"]:
        assert item["store_id"] == store_a.id


def test_get_orders_filter_by_status(orders_env):
    client, token, *_ = orders_env
    response = client.get("/orders?status=delivered", headers=_auth_headers(token))
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["status"] == "delivered"
    assert len(data["items"]) == 2


def test_get_orders_filter_by_notification_status(orders_env):
    client, token, *_ = orders_env
    response = client.get("/orders?notification_status=sent", headers=_auth_headers(token))
    assert response.status_code == 200
    data = response.json()
    for item in data["items"]:
        assert item["notification_status"] == "sent"
    assert len(data["items"]) == 2


def test_get_orders_pagination(orders_env):
    client, token, *_ = orders_env
    r1 = client.get("/orders?page=1&page_size=2", headers=_auth_headers(token))
    assert r1.status_code == 200
    d1 = r1.json()
    assert len(d1["items"]) == 2
    assert d1["total"] == 5
    assert d1["page"] == 1
    assert d1["page_size"] == 2

    r2 = client.get("/orders?page=3&page_size=2", headers=_auth_headers(token))
    d2 = r2.json()
    assert len(d2["items"]) == 1


def test_get_orders_response_schema(orders_env):
    client, token, *_ = orders_env
    response = client.get("/orders?page_size=1", headers=_auth_headers(token))
    data = response.json()
    item = data["items"][0]
    required_fields = [
        "order_id", "store_id", "status", "notification_status",
        "last_message_type", "last_template_name", "last_message_preview",
        "last_notification_at", "error",
    ]
    for field in required_fields:
        assert field in item, f"Missing field: {field}"


def test_get_orders_isolation(orders_env):
    client, token, store_a, store_b, orders_a = orders_env
    response = client.get("/orders", headers=_auth_headers(token))
    data = response.json()
    order_ids = [item["order_id"] for item in data["items"]]
    for oa in orders_a:
        assert oa.id in order_ids
