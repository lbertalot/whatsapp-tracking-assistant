from typing import TYPE_CHECKING, Optional

import phonenumbers

if TYPE_CHECKING:
    from backend.app.models.store import Store, StoreSettings


def normalize_phone(raw: Optional[str], default_region: str = "PY") -> Optional[str]:
    if not raw:
        return None

    try:
        parsed = phonenumbers.parse(raw, default_region)
    except phonenumbers.NumberParseException:
        return None

    if not phonenumbers.is_valid_number(parsed):
        return None

    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def default_region_for_store(store: "Store", settings_row: Optional["StoreSettings"] = None) -> str:
    """ISO-like region for phonenumbers.parse when the number has no country code (LatAm stores)."""
    if (
        settings_row is not None
        and (getattr(settings_row, "default_phone_region", None) or "").strip()
    ):
        return str(settings_row.default_phone_region).strip().upper()[:5]
    c = (store.country or "").strip()
    if len(c) == 2 and c.isalpha():
        return c.upper()
    return "PY"
