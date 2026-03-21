from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    external_id = Column(String(100), nullable=True)
    normalized_phone = Column(String(20), nullable=True)
    tracking_number = Column(String(100), nullable=True)

    current_status = Column(String(50), nullable=True)

    notified_in_transit = Column(Boolean, default=False)
    notified_delivered = Column(Boolean, default=False)

    notification_status = Column(String(50), nullable=True)
    notification_error = Column(Text, nullable=True)
    last_message_type = Column(String(50), nullable=True)
    last_template_name = Column(String(100), nullable=True)
    last_message_preview = Column(Text, nullable=True)

    first_notification_at = Column(DateTime, nullable=True)
    last_notification_at = Column(DateTime, nullable=True)

    invalid_phone = Column(Boolean, default=False)
    last_checked_at = Column(DateTime, nullable=True)
    last_status_change_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="orders")
    notification_attempts = relationship("NotificationAttempt", back_populates="order")

    __table_args__ = (
        Index("idx_orders_store_id", "store_id"),
        Index("idx_orders_current_status", "current_status"),
        Index("idx_orders_store_status", "store_id", "current_status"),
    )
