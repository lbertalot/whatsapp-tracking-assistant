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


def test_build_template_body_components_customer_name_then_order_id():
    c = build_template_body_components({"customer_name": "Ana", "order_id": "352380259"})
    assert c is not None
    params = c[0]["parameters"]
    assert params[0]["text"] == "Ana"
    assert params[1]["text"] == "352380259"


def test_build_template_body_components_blank_customer_name_defaults():
    c = build_template_body_components({"customer_name": "  ", "order_id": "1"})
    params = c[0]["parameters"]
    assert params[0]["text"] == "Cliente"
    assert params[1]["text"] == "1"


def test_build_template_body_components_empty():
    assert build_template_body_components({}) is None


def test_graph_send_error_may_benefit_from_retry():
    assert graph_send_error_may_benefit_from_retry({"success": True}) is False
    assert (
        graph_send_error_may_benefit_from_retry(
            {"success": False, "error": "131047", "error_message": "x"}
        )
        is False
    )
    assert (
        graph_send_error_may_benefit_from_retry(
            {"success": False, "error": "131047:2494010", "error_message": "x"}
        )
        is False
    )
    assert (
        graph_send_error_may_benefit_from_retry(
            {"success": False, "error": "4", "error_message": "limit"}
        )
        is True
    )
    assert (
        graph_send_error_may_benefit_from_retry(
            {"success": False, "error": "transient", "retry_after": "5"}
        )
        is True
    )
    assert (
        graph_send_error_may_benefit_from_retry(
            {"success": False, "error": "not_configured", "error_message": "x"}
        )
        is False
    )
    assert (
        graph_send_error_may_benefit_from_retry(
            {"success": False, "error": "mock_failure", "error_message": "x"}
        )
        is True
    )


def test_graph_error_result_parses_meta_error_and_retry_after():
    import httpx

    resp = httpx.Response(
        404,
        json={
            "error": {
                "message": "(#132001) Template name does not exist",
                "type": "OAuthException",
                "code": 132001,
            }
        },
        headers={"Retry-After": "10"},
    )
    from backend.app.services.whatsapp import graph_error_result

    out = graph_error_result(resp)
    assert out["success"] is False
    assert "132001" in str(out["error"]) or out["error"] in ("132001", "132001:None")
    assert "132001" in out["error_message"] or "does not exist" in out["error_message"]
    assert out["retry_after"] == "10"


def test_graph_error_result_non_json_body():
    import httpx

    resp = httpx.Response(500, content=b"not json")
    from backend.app.services.whatsapp import graph_error_result

    out = graph_error_result(resp)
    assert out["success"] is False
    assert out["error"] == "http_error"
    assert "500" in out["error_message"]


def test_verify_meta_webhook_signature_ok():
    import hashlib
    import hmac

    body = b'{"x":1}'
    secret = "abc"
    good = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_meta_webhook_signature(body, good, secret) is True
    assert verify_meta_webhook_signature(body, "sha256=" + "0" * 64, secret) is False


class TestWhatsAppService:
    def test_real_send_not_configured_missing_phone_id(self):
        svc = WhatsAppService(
            mock=False,
            access_token="tok",
            phone_number_id="",
            template_language="es",
        )
        result = svc.send_template_message(
            to="+595981123456",
            template_name="en_transito",
            params={"order_id": "1"},
        )
        assert result["success"] is False
        assert result.get("error") == "not_configured"

    def test_real_send_not_configured_missing_token(self):
        svc = WhatsAppService(
            mock=False,
            access_token="",
            phone_number_id="123",
            template_language="es",
        )
        result = svc.send_template_message(to="+595981123456", template_name="en_transito")
        assert result["success"] is False
        assert result.get("error") == "not_configured"

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
