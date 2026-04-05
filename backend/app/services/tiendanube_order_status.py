"""Infer internal logistics status from Tiendanube order JSON (source of truth: ecommerce)."""

from __future__ import annotations

import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Normalized lowercase tokens — Tiendanube / Nuvemshop variants differ by store.
_DELIVERED_SHIPPING = frozenset(
    {
        "delivered",
        "entregado",
        "delivery_completed",
        "picked_up",
    }
)
_IN_TRANSIT_SHIPPING = frozenset(
    {
        "shipped",
        "dispatched",
        "in_transit",
        "in transit",
        "enviado",
        "despachado",
        "unpacked",
    }
)
_CANCELLED_SHIPPING = frozenset(
    {
        "cancelled",
        "canceled",
        "cancelado",
        "refunded",
        "void",
    }
)
_CANCELLED_ORDER_STATUS = frozenset(
    {
        "cancelled",
        "canceled",
        "cancelado",
        "refunded",
    }
)


def _norm(value: object) -> str:
    return str(value or "").strip().lower()


def ecommerce_order_cancelled(detail: dict) -> bool:
    """True if payload clearly indicates the order/shipment was cancelled or refunded."""
    if _norm(detail.get("shipping_status")) in _CANCELLED_SHIPPING:
        return True
    if _norm(detail.get("status")) in _CANCELLED_ORDER_STATUS:
        return True
    return False


def tracking_from_order_detail(detail: dict) -> Tuple[Optional[str], Optional[str]]:
    """Same rules as webhooks TN tracking helper (single place for worker + webhooks)."""
    for key in ("fulfillments", "fulfillment_orders"):
        rows = detail.get(key)
        if not isinstance(rows, list):
            continue
        for fo in rows:
            if not isinstance(fo, dict):
                continue
            info = fo.get("tracking_info")
            if isinstance(info, dict) and info.get("code"):
                u = info.get("url")
                return str(info["code"]), str(u) if u else None
    return None, None


def map_tiendanube_order_detail(detail: dict, *, order_id: Optional[int] = None) -> Optional[str]:
    """
    Map TN order payload to internal status: in_transit | delivered | None.

    Precedence: (1) shipping_status, (2) fulfillment_orders[].status,
    (3) order status + closed hints, (4) tracking code only if no cancel signal.
    """
    if not detail:
        return None

    if ecommerce_order_cancelled(detail):
        logger.debug(
            "map_tiendanube_order_detail order_id=%s: cancel signal, skip in_transit fallback",
            order_id,
        )
        return None

    ship = _norm(detail.get("shipping_status"))

    # Priority 1 — primary TN field
    if ship in _DELIVERED_SHIPPING:
        logger.debug("order_id=%s shipping_status=%r -> delivered", order_id, ship)
        return "delivered"
    if ship in _IN_TRANSIT_SHIPPING:
        logger.debug("order_id=%s shipping_status=%r -> in_transit", order_id, ship)
        return "in_transit"

    # Priority 2 — fulfillment rows
    fos = detail.get("fulfillment_orders")
    if isinstance(fos, list):
        for fo in fos:
            if not isinstance(fo, dict):
                continue
            st = _norm(fo.get("status"))
            if st in _CANCELLED_ORDER_STATUS:
                logger.debug("order_id=%s fulfillment status=%r -> cancelled", order_id, st)
                return None
            if "deliver" in st or st in ("delivered", "completed"):
                logger.debug("order_id=%s fulfillment status=%r -> delivered", order_id, st)
                return "delivered"
            if st in ("shipped", "fulfilled", "in_progress", "open", "partially_fulfilled"):
                logger.debug("order_id=%s fulfillment status=%r -> in_transit", order_id, st)
                return "in_transit"

    order_status = _norm(detail.get("status"))
    if order_status in _CANCELLED_ORDER_STATUS:
        return None

    # Priority 3 — closed order + hints
    if order_status == "closed":
        if detail.get("delivered_at") or ship in _DELIVERED_SHIPPING:
            return "delivered"
        code, _ = tracking_from_order_detail(detail)
        if code and ship not in ("unshipped", "unfulfilled", ""):
            out = "delivered" if ship in _DELIVERED_SHIPPING else "in_transit"
            logger.debug("order_id=%s closed order hint -> %s", order_id, out)
            return out

    # Priority 4 — tracking only if still no cancel signal
    code, _ = tracking_from_order_detail(detail)
    if code:
        logger.debug("order_id=%s tracking code present -> in_transit", order_id)
        return "in_transit"

    logger.debug("order_id=%s: no mapped status", order_id)
    return None
