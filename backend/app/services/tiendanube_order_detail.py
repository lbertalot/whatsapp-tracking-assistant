"""Shared helpers for Tiendanube order JSON (webhooks, bulk import, worker)."""

from __future__ import annotations

from typing import Optional, Tuple


def customer_fields_from_order_detail(detail: dict) -> Tuple[Optional[str], Optional[str]]:
    """Extract contact phone and display name from TN order detail or list payload."""
    customer = detail.get("customer") if isinstance(detail.get("customer"), dict) else {}
    raw_phone = detail.get("contact_phone") or customer.get("phone") or detail.get("billing_phone")
    if raw_phone is not None:
        raw_phone = str(raw_phone).strip() or None
    name = detail.get("contact_name") or customer.get("name")
    if name is not None:
        name = str(name).strip() or None
    return raw_phone, name
