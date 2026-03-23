import hashlib
import hmac
import logging
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import httpx

from backend.app.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def build_template_body_components(params: Dict[str, Any]) -> Optional[List[dict]]:
    """Arma `template.components` si el body de la plantilla tiene variables.

    Orden: `order_id` primero; luego demás claves alfabéticamente.
    """
    if not params:
        return None
    texts: List[str] = []
    if "order_id" in params:
        texts.append(str(params["order_id"]))
    for key in sorted(params.keys()):
        if key == "order_id":
            continue
        texts.append(str(params[key]))
    if not texts:
        return None
    parameters = [{"type": "text", "text": t} for t in texts]
    return [{"type": "body", "parameters": parameters}]


def verify_meta_webhook_signature(
    body: bytes, signature_header: Optional[str], app_secret: str
) -> bool:
    """Valida cabecera X-Hub-Signature-256 (sha256=<hex>)."""
    if not app_secret or not signature_header:
        return False
    if not signature_header.startswith("sha256="):
        return False
    expected_hex = signature_header[7:]
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, expected_hex)


def graph_error_result(resp: httpx.Response) -> dict:
    """Parsea cuerpo JSON de error Graph y metadatos HTTP (p. ej. Retry-After)."""
    code = "http_error"
    message = f"HTTP {resp.status_code}"
    retry_after = resp.headers.get("Retry-After")
    try:
        data = resp.json()
        err = data.get("error")
        if isinstance(err, dict):
            c = err.get("code")
            sub = err.get("error_subcode")
            if c is not None:
                code = str(c) if sub is None else f"{c}:{sub}"
            message = err.get("message", message) or message
    except Exception:
        pass
    if retry_after:
        message = f"{message} (Retry-After: {retry_after})"
    return {
        "success": False,
        "error": code,
        "error_message": message,
        "retry_after": retry_after,
    }


# Códigos Graph (base, antes de ":") donde repetir el mismo envío en segundos suele ser inútil.
# Lista conservadora; ampliar según telemetría. Ver MS-I06 en MILESTONES.md.
_GRAPH_SEND_NO_RETRY_BASE_CODES = frozenset(
    {
        "100",  # Invalid parameter
        "131047",  # Re-engagement / ventana de servicio
        "131026",  # Undeliverable
        "131051",  # Unsupported message type
        "132000",  # Template / parámetros
        "131009",  # Permission
        "190",  # Invalid OAuth / token
        "131031",  # Locked
        "368",  # Temporary block / policy
    }
)


def graph_send_error_may_benefit_from_retry(result: dict) -> bool:
    """
    Indica si tiene sentido otro intento inmediato con el mismo payload.
    `mock_failure` siempre True para no romper tests que simulan reintentos.
    """
    if result.get("success"):
        return False
    if result.get("retry_after"):
        return True
    err = str(result.get("error") or "")
    if err == "mock_failure":
        return True
    if err == "not_configured":
        return False
    if err == "request_error":
        return True
    base = err.split(":")[0]
    if base in _GRAPH_SEND_NO_RETRY_BASE_CODES:
        return False
    return True


class WhatsAppService:
    def __init__(
        self,
        mock: bool = False,
        force_fail: bool = False,
        *,
        api_url: Optional[str] = None,
        access_token: Optional[str] = None,
        phone_number_id: Optional[str] = None,
        template_language: str = "es",
    ):
        self.mock = mock
        self.force_fail = force_fail
        self.api_url = api_url if api_url is not None else settings.WHATSAPP_API_URL
        self.access_token = (
            access_token if access_token is not None else settings.WHATSAPP_ACCESS_TOKEN
        )
        self.phone_number_id = (
            phone_number_id if phone_number_id is not None else settings.WHATSAPP_PHONE_NUMBER_ID
        )
        self.template_language = (template_language or "es").strip() or "es"

    @staticmethod
    def resolve_for_store(db: "Session", store_id: int) -> "WhatsAppService":
        """Credenciales por tienda (MS-I08); fallback global si WHATSAPP_ALLOW_GLOBAL_FALLBACK."""
        from backend.app.models.store import StoreSettings

        row = db.query(StoreSettings).filter(StoreSettings.store_id == store_id).first()
        lang = "es"
        if row and (row.whatsapp_template_language or "").strip():
            lang = row.whatsapp_template_language.strip()

        token = (row.whatsapp_access_token or "").strip() if row else ""
        pnid = (row.whatsapp_phone_number_id or "").strip() if row else ""

        if token and pnid:
            return WhatsAppService(
                mock=False,
                access_token=token,
                phone_number_id=pnid,
                template_language=lang,
            )

        if settings.WHATSAPP_ALLOW_GLOBAL_FALLBACK:
            gt = (settings.WHATSAPP_ACCESS_TOKEN or "").strip()
            gp = (settings.WHATSAPP_PHONE_NUMBER_ID or "").strip()
            if gt and gp:
                return WhatsAppService(mock=False, template_language=lang)

        if settings.APP_ENV in ("testing", "development"):
            return WhatsAppService(mock=True, template_language=lang)

        return WhatsAppService(
            mock=False,
            access_token="",
            phone_number_id="",
            template_language=lang,
        )

    def send_template_message(
        self,
        to: str,
        template_name: str,
        params: Optional[Dict] = None,
        language: Optional[str] = None,
    ) -> dict:
        if self.mock:
            return self._mock_send(to, template_name)

        lang = (language or self.template_language or "es").strip() or "es"
        return self._real_send(to, template_name, params or {}, lang)

    def _mock_send(self, to: str, template_name: str) -> dict:
        if self.force_fail:
            return {
                "success": False,
                "error": "mock_failure",
                "error_message": "Simulated WhatsApp send failure",
            }
        return {
            "success": True,
            "message_id": f"wamid.mock_{uuid.uuid4().hex[:12]}",
        }

    def _real_send(self, to: str, template_name: str, params: dict, language: str) -> dict:
        if not (self.phone_number_id or "").strip():
            return {
                "success": False,
                "error": "not_configured",
                "error_message": "WhatsApp phone_number_id no configurado para esta tienda",
            }
        if not (self.access_token or "").strip():
            return {
                "success": False,
                "error": "not_configured",
                "error_message": "WhatsApp access_token no configurado para esta tienda",
            }
        url = f"{self.api_url.rstrip('/')}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        template_block: Dict[str, Any] = {
            "name": template_name,
            "language": {"code": language},
        }
        components = build_template_body_components(params)
        if components is not None:
            template_block["components"] = components

        body = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": template_block,
        }

        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=10.0)
            if resp.status_code >= 400:
                err_code = None
                try:
                    err_code = (resp.json().get("error") or {}).get("code")
                except Exception:
                    pass
                logger.warning(
                    "WhatsApp API HTTP %s for template=%s (code=%s)",
                    resp.status_code,
                    template_name,
                    err_code,
                )
                return graph_error_result(resp)
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"success": True, "message_id": msg_id}
        except httpx.RequestError as e:
            logger.error("WhatsApp API request error: %s", e)
            return {
                "success": False,
                "error": "request_error",
                "error_message": str(e),
            }
