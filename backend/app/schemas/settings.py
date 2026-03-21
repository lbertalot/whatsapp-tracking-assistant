from typing import Optional

from pydantic import BaseModel


class StoreSettingsResponse(BaseModel):
    model_config = {"from_attributes": True}

    template_in_transit: Optional[str] = None
    template_delivered: Optional[str] = None
    weraha_enabled: bool = False
    weraha_account_reference: Optional[str] = None
    whatsapp_enabled: bool = False
    whatsapp_phone_number_id: Optional[str] = None
    onboarding_status: str = "pending"
    test_message_status: Optional[str] = None


class StoreSettingsUpdate(BaseModel):
    template_in_transit: Optional[str] = None
    template_delivered: Optional[str] = None
    weraha_account_reference: Optional[str] = None
