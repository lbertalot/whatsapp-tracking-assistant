from typing import Optional

import phonenumbers


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
