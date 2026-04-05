from typing import Optional

from pydantic import BaseModel


class OnboardingStatusResponse(BaseModel):
    needs_tiendanube: bool
    tiendanube_user_id: Optional[str] = None
    installation_active: bool
    onboarding_status: str
    store_name: str
    # MS-ONB03: True después de la primera importación bulk (o si no aplica aún).
    initial_orders_import_completed: bool = False
    # URLs públicas que el comercio o soporte pueden verificar en el portal de socios TN
    oauth_callback_url: str
    webhook_public_url: str
    tiendanube_app_configured: bool


class TiendanubeInstallUrlResponse(BaseModel):
    url: str
