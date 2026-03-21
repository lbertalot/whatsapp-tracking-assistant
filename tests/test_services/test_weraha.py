from backend.app.services.weraha import WerahaAdapter


class TestWerahaAdapter:
    def test_mock_returns_status(self):
        adapter = WerahaAdapter(api_url="https://mock", api_key="test-key")
        result = adapter.get_tracking_status("WRH-001")
        assert "status" in result
        assert isinstance(result["status"], str)
        assert len(result["status"]) > 0

    def test_mock_returns_raw_events(self):
        adapter = WerahaAdapter(api_url="https://mock", api_key="test-key")
        result = adapter.get_tracking_status("WRH-002")
        assert "tracking_number" in result
        assert result["tracking_number"] == "WRH-002"
