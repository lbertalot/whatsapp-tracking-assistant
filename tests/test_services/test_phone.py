from backend.app.services.phone import normalize_phone


class TestNormalizePhone:
    def test_paraguayan_mobile_with_country_code(self):
        assert normalize_phone("+595981123456") == "+595981123456"

    def test_paraguayan_mobile_without_plus(self):
        assert normalize_phone("595981123456") == "+595981123456"

    def test_paraguayan_mobile_local_format(self):
        assert normalize_phone("0981123456", default_region="PY") == "+595981123456"

    def test_paraguayan_mobile_no_leading_zero(self):
        assert normalize_phone("981123456", default_region="PY") == "+595981123456"

    def test_invalid_phone_returns_none(self):
        assert normalize_phone("123") is None

    def test_empty_string_returns_none(self):
        assert normalize_phone("") is None

    def test_none_input_returns_none(self):
        assert normalize_phone(None) is None

    def test_garbage_returns_none(self):
        assert normalize_phone("not-a-phone") is None

    def test_international_format_preserved(self):
        assert normalize_phone("+14155552671") == "+14155552671"
