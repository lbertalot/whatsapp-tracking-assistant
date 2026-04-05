from backend.app.services.tiendanube_order_status import (
    ecommerce_order_cancelled,
    map_tiendanube_order_detail,
    tracking_from_order_detail,
)


def test_map_delivered_from_shipping_status():
    assert map_tiendanube_order_detail({"shipping_status": "delivered"}) == "delivered"


def test_map_in_transit_from_shipping_status():
    assert map_tiendanube_order_detail({"shipping_status": "shipped"}) == "in_transit"


def test_map_in_transit_from_tracking_only():
    d = {"fulfillment_orders": [{"tracking_info": {"code": "ABC123"}}]}
    assert map_tiendanube_order_detail(d) == "in_transit"


def test_cancelled_with_tracking_returns_none():
    d = {
        "shipping_status": "cancelled",
        "fulfillment_orders": [{"tracking_info": {"code": "ABC123"}}],
    }
    assert map_tiendanube_order_detail(d, order_id=99) is None


def test_empty_merged_dict_returns_none():
    assert map_tiendanube_order_detail({}) is None


def test_ecommerce_order_cancelled_helper():
    assert ecommerce_order_cancelled({"status": "cancelled"}) is True
    assert ecommerce_order_cancelled({"shipping_status": "shipped"}) is False


def test_tracking_from_order_detail():
    d = {
        "fulfillment_orders": [
            {"tracking_info": {"code": "X1", "url": "https://t.example/x"}},
        ]
    }
    code, url = tracking_from_order_detail(d)
    assert code == "X1"
    assert url == "https://t.example/x"
