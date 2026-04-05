import logging
from typing import Optional
from urllib.parse import quote

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


class TiendanubeService:
    def __init__(self):
        self.app_id = settings.TIENDANUBE_APP_ID
        self.client_secret = settings.TIENDANUBE_CLIENT_SECRET
        self.token_url = settings.TIENDANUBE_TOKEN_URL
        self.api_url = settings.TIENDANUBE_API_URL
        self.base_url = settings.APP_BASE_URL

    def get_auth_url(self, state: Optional[str] = None) -> str:
        """URL de autorización TN. Opcional: TIENDANUBE_OAUTH_SCOPE y state (JWT OAuth)."""
        base = settings.TIENDANUBE_AUTH_URL.format(app_id=self.app_id)
        scope = (settings.TIENDANUBE_OAUTH_SCOPE or "").strip()
        parts: list[str] = []
        if scope:
            parts.append(f"scope={quote(scope, safe='')}")
        if state:
            parts.append(f"state={quote(state, safe='')}")
        if not parts:
            return base
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{'&'.join(parts)}"

    def get_callback_url(self) -> str:
        return f"{self.base_url}/integrations/tiendanube/callback"

    def exchange_code(self, code: str) -> dict:
        # Tiendanube acepta JSON en POST /apps/authorize/token (documentación / ejemplos oficiales)
        resp = httpx.post(
            self.token_url,
            json={
                "client_id": self.app_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "code": code,
            },
            headers={"Content-Type": "application/json"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_store_info(self, user_id: int, access_token: str) -> dict:
        resp = httpx.get(
            f"{self.api_url}/{user_id}/store",
            headers={"Authentication": f"bearer {access_token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()

    def fetch_orders(
        self,
        user_id: int,
        access_token: str,
        *,
        page: int = 1,
        per_page: int = 100,
        aggregates: Optional[str] = "fulfillment_orders",
        timeout: float = 45.0,
    ) -> list[dict]:
        """GET /{user_id}/orders — paginated list (Nuvemshop returns a JSON array)."""
        per_page = min(max(per_page, 1), 200)
        page = max(page, 1)
        params: dict[str, int | str] = {"page": page, "per_page": per_page}
        if aggregates:
            params["aggregates"] = aggregates
        resp = httpx.get(
            f"{self.api_url}/{user_id}/orders",
            headers={"Authentication": f"bearer {access_token}"},
            params=params,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            logger.warning("TN fetch_orders: unexpected JSON type %s", type(data))
            return []
        return data

    def fetch_order(
        self,
        user_id: int,
        order_id: int,
        access_token: str,
        *,
        aggregates: Optional[str] = None,
        timeout: float = 2.5,
    ) -> dict:
        """GET /{user_id}/orders/{order_id} — usar aggregates=fulfillment_orders para tracking."""
        params = {}
        if aggregates:
            params["aggregates"] = aggregates
        resp = httpx.get(
            f"{self.api_url}/{user_id}/orders/{order_id}",
            headers={"Authentication": f"bearer {access_token}"},
            params=params or None,
            timeout=timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def register_webhooks(self, user_id: int, access_token: str) -> None:
        events = ["order/created", "order/paid", "order/fulfilled"]
        for event in events:
            try:
                httpx.post(
                    f"{self.api_url}/{user_id}/webhooks",
                    headers={
                        "Authentication": f"bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "event": event,
                        "url": f"{self.base_url}/webhooks/tiendanube",
                    },
                    timeout=10.0,
                )
            except httpx.HTTPError as e:
                logger.warning("Failed to register webhook %s: %s", event, e)
