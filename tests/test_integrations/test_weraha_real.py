from unittest.mock import MagicMock, patch

import httpx

from backend.app.services.state_mapper import map_raw_status
from backend.app.services.weraha import WerahaAdapter


class TestWerahaReal:
    def _adapter(self):
        return WerahaAdapter(api_url="https://api.weraha.com.py", api_key="test-key")

    def test_real_success(self):
        adapter = self._adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tracking_number": "WRH-100",
            "status": "EN_CAMINO",
            "events": [{"status": "EN_CAMINO", "date": "2026-03-20"}],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.app.services.weraha.httpx.get", return_value=mock_resp):
            result = adapter.get_tracking_status("WRH-100")

        assert result["status"] == "EN_CAMINO"
        assert result["tracking_number"] == "WRH-100"

    def test_real_not_found(self):
        adapter = self._adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=MagicMock(), response=mock_resp
        )

        with patch("backend.app.services.weraha.httpx.get", return_value=mock_resp):
            result = adapter.get_tracking_status("WRH-NONEXISTENT")

        assert "error" in result

    def test_real_timeout(self):
        adapter = self._adapter()

        with patch(
            "backend.app.services.weraha.httpx.get",
            side_effect=httpx.TimeoutException("Timeout"),
        ):
            result = adapter.get_tracking_status("WRH-TIMEOUT")

        assert "error" in result

    def test_real_auth_error(self):
        adapter = self._adapter()
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=MagicMock(), response=mock_resp
        )

        with patch("backend.app.services.weraha.httpx.get", return_value=mock_resp):
            result = adapter.get_tracking_status("WRH-UNAUTH")

        assert "error" in result

    def test_state_mapper_with_real_states(self):
        real_states = {
            "EN_CAMINO": "in_transit",
            "ENTREGADO": "delivered",
            "IN_TRANSIT": "in_transit",
            "DELIVERED": "delivered",
            "En Camino": "in_transit",
            "Delivered": "delivered",
        }
        for raw, expected in real_states.items():
            assert map_raw_status(raw) == expected, f"Failed for raw={raw}"
