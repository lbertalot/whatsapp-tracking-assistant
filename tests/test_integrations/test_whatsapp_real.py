from unittest.mock import patch, MagicMock

import httpx
import pytest

from backend.app.services.whatsapp import WhatsAppService


class TestWhatsAppReal:
    def _service(self):
        svc = WhatsAppService(mock=False)
        svc.api_url = "https://graph.facebook.com/v21.0"
        svc.access_token = "test-token"
        svc.phone_number_id = "123456789"
        return svc

    def test_real_send_success(self):
        svc = self._service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "messaging_product": "whatsapp",
            "contacts": [{"input": "+595981123456", "wa_id": "595981123456"}],
            "messages": [{"id": "wamid.real_abc123"}],
        }
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.app.services.whatsapp.httpx.post", return_value=mock_resp):
            result = svc.send_template_message(
                to="+595981123456",
                template_name="shipping_in_transit_v1",
            )

        assert result["success"] is True
        assert result["message_id"] == "wamid.real_abc123"

    def test_real_send_failure(self):
        svc = self._service()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad Request", request=MagicMock(), response=mock_resp
        )

        with patch("backend.app.services.whatsapp.httpx.post", return_value=mock_resp):
            result = svc.send_template_message(
                to="+595981123456",
                template_name="shipping_in_transit_v1",
            )

        assert result["success"] is False
        assert "error" in result

    def test_real_rate_limit(self):
        svc = self._service()
        mock_resp = MagicMock()
        mock_resp.status_code = 429
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Rate limited", request=MagicMock(), response=mock_resp
        )

        with patch("backend.app.services.whatsapp.httpx.post", return_value=mock_resp):
            result = svc.send_template_message(
                to="+595981123456",
                template_name="shipping_in_transit_v1",
            )

        assert result["success"] is False

    def test_real_invalid_phone(self):
        svc = self._service()
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Invalid phone", request=MagicMock(), response=mock_resp
        )

        with patch("backend.app.services.whatsapp.httpx.post", return_value=mock_resp):
            result = svc.send_template_message(
                to="invalid",
                template_name="shipping_in_transit_v1",
            )

        assert result["success"] is False

    def test_template_body_correct(self):
        svc = self._service()
        captured_kwargs = {}

        def capture_post(url, **kwargs):
            captured_kwargs.update(kwargs)
            mock_r = MagicMock()
            mock_r.status_code = 200
            mock_r.json.return_value = {"messages": [{"id": "wamid.test"}]}
            mock_r.raise_for_status = MagicMock()
            return mock_r

        with patch("backend.app.services.whatsapp.httpx.post", side_effect=capture_post):
            svc.send_template_message(
                to="+595981123456",
                template_name="shipping_in_transit_v1",
                language="es",
            )

        body = captured_kwargs["json"]
        assert body["messaging_product"] == "whatsapp"
        assert body["to"] == "+595981123456"
        assert body["type"] == "template"
        assert body["template"]["name"] == "shipping_in_transit_v1"
        assert body["template"]["language"]["code"] == "es"

    def test_whatsapp_test_message(self):
        svc = self._service()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"messages": [{"id": "wamid.test_msg"}]}
        mock_resp.raise_for_status = MagicMock()

        with patch("backend.app.services.whatsapp.httpx.post", return_value=mock_resp):
            result = svc.send_template_message(
                to="+595981000000",
                template_name="shipping_in_transit_v1",
                params={"order_id": "TEST-001"},
            )

        assert result["success"] is True
