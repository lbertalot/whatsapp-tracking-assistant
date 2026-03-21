from typing import Optional

_IN_TRANSIT = {"en_camino", "en camino", "in_transit", "in transit"}
_DELIVERED = {"entregado", "delivered"}


def map_raw_status(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None

    normalized = raw.strip().lower()

    if normalized in _IN_TRANSIT:
        return "in_transit"
    if normalized in _DELIVERED:
        return "delivered"

    return None
