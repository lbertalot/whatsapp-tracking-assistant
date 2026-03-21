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


class OrderListItem(BaseModel):
    model_config = {"from_attributes": True}

    order_id: int
    store_id: int
    status: Optional[str] = None
    notification_status: Optional[str] = None
    last_message_type: Optional[str] = None
    last_template_name: Optional[str] = None
    last_message_preview: Optional[str] = None
    last_notification_at: Optional[str] = None
    error: Optional[str] = None


class OrderListResponse(BaseModel):
    items: list[OrderListItem]
    total: int
    page: int
    page_size: int
