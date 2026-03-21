from backend.app.services.whatsapp import WhatsAppService


class TestWhatsAppService:
    def test_mock_send_success(self):
        svc = WhatsAppService(mock=True)
        result = svc.send_template_message(
            to="+595981123456",
            template_name="shipping_in_transit_v1",
            params={"order_number": "123"},
        )
        assert result["success"] is True
        assert "message_id" in result
        assert len(result["message_id"]) > 0

    def test_mock_send_failure(self):
        svc = WhatsAppService(mock=True, force_fail=True)
        result = svc.send_template_message(
            to="+595981123456",
            template_name="shipping_in_transit_v1",
            params={"order_number": "123"},
        )
        assert result["success"] is False
        assert "error" in result
