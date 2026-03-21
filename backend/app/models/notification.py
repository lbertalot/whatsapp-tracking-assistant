from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class NotificationAttempt(Base):
    __tablename__ = "notification_attempts"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    idempotency_key = Column(String(255), nullable=False, unique=True)
    template_name = Column(String(100), nullable=True)
    status = Column(String(50), nullable=False)
    provider_message_id = Column(String(150), nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    attempt_number = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("Order", back_populates="notification_attempts")

    __table_args__ = (
        Index("idx_notification_attempts_order", "order_id"),
        Index("idx_notification_attempts_store", "store_id"),
    )
