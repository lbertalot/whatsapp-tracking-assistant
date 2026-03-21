import logging
import uuid
from typing import Dict, Optional

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class WhatsAppService:
    def __init__(self, mock: bool = False, force_fail: bool = False):
        self.mock = mock
        self.force_fail = force_fail
        self.api_url = settings.WHATSAPP_API_URL
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID

    def send_template_message(
        self,
        to: str,
        template_name: str,
        params: Optional[Dict] = None,
        language: str = "es",
    ) -> dict:
        if self.mock:
            return self._mock_send(to, template_name)

        return self._real_send(to, template_name, params or {}, language)

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

    def _real_send(
        self, to: str, template_name: str, params: dict, language: str
    ) -> dict:
        url = f"{self.api_url}/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }
        body = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }

        try:
            resp = httpx.post(url, json=body, headers=headers, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            msg_id = data.get("messages", [{}])[0].get("id", "")
            return {"success": True, "message_id": msg_id}
        except httpx.HTTPError as e:
            logger.error("WhatsApp API error: %s", e)
            return {
                "success": False,
                "error": "api_error",
                "error_message": str(e),
            }
