from typing import Optional

from pydantic import BaseModel


class WebhookCustomer(BaseModel):
    phone: Optional[str] = None
    name: Optional[str] = None


class WebhookOrderPayload(BaseModel):
    store_id: str
    id: str
    number: Optional[int] = None
    customer: Optional[WebhookCustomer] = None
    shipping_tracking_number: Optional[str] = None
    shipping_tracking_url: Optional[str] = None


class WebhookOrderResponse(BaseModel):
    status: str
    order_id: int
    invalid_phone: Optional[bool] = None
