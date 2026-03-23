from typing import Optional

from pydantic import BaseModel, Field

from backend.app.models.store import StoreSettings


class StoreSettingsResponse(BaseModel):
    """Nunca expone `whatsapp_access_token` en JSON; solo si hay token guardado."""

    template_in_transit: Optional[str] = None
    template_delivered: Optional[str] = None
    weraha_enabled: bool = False
    weraha_account_reference: Optional[str] = None
    whatsapp_enabled: bool = False
    whatsapp_include_body_params: bool = True
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_token_configured: bool = False
    whatsapp_template_language: str = "es"
    onboarding_status: str = "pending"
    test_message_status: Optional[str] = None

    @classmethod
    def from_store_settings(cls, s: StoreSettings) -> "StoreSettingsResponse":
        return cls(
            template_in_transit=s.template_in_transit,
            template_delivered=s.template_delivered,
            weraha_enabled=bool(s.weraha_enabled),
            weraha_account_reference=s.weraha_account_reference,
            whatsapp_enabled=bool(s.whatsapp_enabled),
            whatsapp_include_body_params=(
                True
                if getattr(s, "whatsapp_include_body_params", None) is None
                else bool(s.whatsapp_include_body_params)
            ),
            whatsapp_phone_number_id=s.whatsapp_phone_number_id,
            whatsapp_token_configured=bool((s.whatsapp_access_token or "").strip()),
            whatsapp_template_language=(s.whatsapp_template_language or "es").strip() or "es",
            onboarding_status=s.onboarding_status or "pending",
            test_message_status=s.test_message_status,
        )


class StoreSettingsUpdate(BaseModel):
    template_in_transit: Optional[str] = None
    template_delivered: Optional[str] = None
    weraha_account_reference: Optional[str] = None
    whatsapp_enabled: Optional[bool] = None
    whatsapp_include_body_params: Optional[bool] = None
    whatsapp_phone_number_id: Optional[str] = None
    whatsapp_access_token: Optional[str] = Field(
        default=None,
        description=("Token Meta; omitir para no cambiar; '' explícito borra el valor guardado"),
    )
    whatsapp_template_language: Optional[str] = Field(
        default=None,
        description="Código de idioma de plantilla (ej. es, es_AR)",
    )
