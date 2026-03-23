from typing import Optional

from pydantic import BaseModel


class OnboardingStatusResponse(BaseModel):
    needs_tiendanube: bool
    tiendanube_user_id: Optional[str] = None
    installation_active: bool
    onboarding_status: str
    store_name: str
    # URLs públicas que el comercio o soporte pueden verificar en el portal de socios TN
    oauth_callback_url: str
    webhook_public_url: str
    tiendanube_app_configured: bool


class TiendanubeInstallUrlResponse(BaseModel):
    url: str
