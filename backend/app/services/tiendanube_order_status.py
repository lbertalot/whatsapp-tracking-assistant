"""Infer internal logistics status from Tiendanube order JSON (source of truth: ecommerce)."""

from __future__ import annotations

from typing import Any, Optional, Tuple


def tracking_from_order_detail(detail: dict) -> Tuple[Optional[str], Optional[str]]:
    """Same rules as webhooks_tn._tracking_from_order_detail (single place for worker + webhooks)."""
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


def map_tiendanube_order_detail(detail: dict) -> Optional[str]:
    """
    Map TN order payload to internal status: in_transit | delivered | None.

    Tiendanube/Nuvemshop fields vary; we combine shipping_status, fulfillment_orders,
    order status and optional delivered_at-style hints.
    """
    if not detail:
        return None

    ship = str(detail.get("shipping_status") or "").strip().lower()
    if ship in ("delivered", "entregado", "delivery_completed", "picked_up"):
        return "delivered"
    if ship in (
        "shipped",
        "dispatched",
        "in_transit",
        "in transit",
        "enviado",
        "despachado",
        "unpacked",
    ):
        return "in_transit"

    fos = detail.get("fulfillment_orders")
    if isinstance(fos, list):
        for fo in fos:
            if not isinstance(fo, dict):
                continue
            st = str(fo.get("status") or "").strip().lower()
            if "deliver" in st or st in ("delivered", "completed"):
                return "delivered"
            if st in ("shipped", "fulfilled", "in_progress", "open", "partially_fulfilled"):
                return "in_transit"

    order_status = str(detail.get("status") or "").strip().lower()
    if order_status == "closed":
        if detail.get("delivered_at") or ship in ("delivered", "entregado"):
            return "delivered"
        code, _ = tracking_from_order_detail(detail)
        if code and ship not in ("unshipped", "unfulfilled", ""):
            return "delivered" if ship in ("delivered", "entregado") else "in_transit"

    code, _ = tracking_from_order_detail(detail)
    if code:
        return "in_transit"

    return None
