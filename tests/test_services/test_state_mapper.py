from backend.app.services.state_mapper import map_raw_status


class TestStateMapper:
    def test_in_transit_variants(self):
        for raw in ["EN_CAMINO", "en_camino", "EN CAMINO", "In Transit", "IN_TRANSIT"]:
            assert map_raw_status(raw) == "in_transit", f"Failed for: {raw}"

    def test_delivered_variants(self):
        for raw in ["ENTREGADO", "entregado", "DELIVERED", "Delivered"]:
            assert map_raw_status(raw) == "delivered", f"Failed for: {raw}"

    def test_unknown_returns_none(self):
        assert map_raw_status("UNKNOWN_STATUS_XYZ") is None

    def test_empty_returns_none(self):
        assert map_raw_status("") is None
        assert map_raw_status(None) is None
