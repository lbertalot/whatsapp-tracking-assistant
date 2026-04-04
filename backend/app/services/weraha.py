import logging
from typing import Optional

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class WerahaAdapter:
    """Adapter HTTP hacia Weraha (MS-I03). Contrato por tienda: header opcional de cuenta."""

    def __init__(self, api_url: str = "", api_key: str = ""):
        self.api_url = api_url or settings.WERAHA_API_URL
        self.api_key = api_key or settings.WERAHA_API_KEY

    def get_tracking_status(
        self,
        tracking_number: str,
        *,
        account_reference: Optional[str] = None,
    ) -> dict:
        """
        GET `{api_url}/tracking/{tracking_number}` con Bearer global.

        Si `account_reference` (p. ej. `StoreSettings.weraha_account_reference`) no está vacío,
        se envía cabecera **X-Weraha-Account-Ref** para integraciones multi-cuenta.
        Contrato oficial Weraha en producción puede diferir — ajustar en MS-I03 según proveedor.
        """
        if not self.api_url or self.api_url == "https://mock":
            return self._mock_response(tracking_number)

        headers = {"Authorization": f"Bearer {self.api_key}"}
        ref = (account_reference or "").strip()
        if ref:
            headers["X-Weraha-Account-Ref"] = ref

        try:
            response = httpx.get(
                f"{self.api_url}/tracking/{tracking_number}",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error("Weraha API error for %s: %s", tracking_number, e)
            return {"tracking_number": tracking_number, "status": "", "error": str(e)}

    def _mock_response(self, tracking_number: str) -> dict:
        return {
            "tracking_number": tracking_number,
            "status": "EN_CAMINO",
        }
