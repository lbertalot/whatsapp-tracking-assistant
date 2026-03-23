from backend.app.services.whatsapp import (
    WhatsAppService,
    build_template_body_components,
    graph_send_error_may_benefit_from_retry,
    verify_meta_webhook_signature,
)


def test_build_template_body_components_order_id_first():
    c = build_template_body_components({"order_id": "TN-99", "extra": "x"})
    assert c is not None
    assert c[0]["type"] == "body"
    params = c[0]["parameters"]
    assert params[0]["text"] == "TN-99"
    assert params[1]["text"] == "x"


def test_build_template_body_components_empty():
    assert build_template_body_components({}) is None


def test_graph_send_error_may_benefit_from_retry():
    assert graph_send_error_may_benefit_from_retry({"success": True}) is False
    assert graph_send_error_may_benefit_from_retry(
        {"success": False, "error": "131047", "error_message": "x"}
    ) is False
    assert graph_send_error_may_benefit_from_retry(
        {"success": False, "error": "131047:2494010", "error_message": "x"}
    ) is False
    assert graph_send_error_may_benefit_from_retry(
        {"success": False, "error": "4", "error_message": "limit"}
    ) is True
    assert graph_send_error_may_benefit_from_retry(
        {"success": False, "error": "transient", "retry_after": "5"}
    ) is True
    assert graph_send_error_may_benefit_from_retry(
        {"success": False, "error": "not_configured", "error_message": "x"}
    ) is False
    assert graph_send_error_may_benefit_from_retry(
        {"success": False, "error": "mock_failure", "error_message": "x"}
    ) is True


def test_verify_meta_webhook_signature_ok():
    import hashlib
    import hmac

    body = b'{"x":1}'
    secret = "abc"
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_meta_webhook_signature(body, good, secret) is True
    assert verify_meta_webhook_signature(body, "sha256=" + "0" * 64, secret) is False


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
