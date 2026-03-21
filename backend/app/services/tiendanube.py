import logging
from typing import Optional

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

    def get_auth_url(self) -> str:
        return (
            settings.TIENDANUBE_AUTH_URL.format(app_id=self.app_id)
        )

    def get_callback_url(self) -> str:
        return f"{self.base_url}/integrations/tiendanube/callback"

    def exchange_code(self, code: str) -> dict:
        resp = httpx.post(
            self.token_url,
            data={
                "client_id": self.app_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "code": code,
            },
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
                    json={"event": event, "url": f"{self.base_url}/webhooks/tiendanube"},
                    timeout=10.0,
                )
            except httpx.HTTPError as e:
                logger.warning("Failed to register webhook %s: %s", event, e)
