from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    external_store_id = Column(String(100), unique=True, nullable=True)
    name = Column(String(150), nullable=False)
    country = Column(String(50), default="Paraguay")
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    settings = relationship("StoreSettings", back_populates="store", uselist=False)
    installations = relationship("StoreInstallation", back_populates="store")
    users = relationship("StoreUser", back_populates="store")
    orders = relationship("Order", back_populates="store")


class StoreInstallation(Base):
    __tablename__ = "store_installations"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False)
    order_source_type = Column(String(50), nullable=False)
    installed_at = Column(DateTime, nullable=True)
    access_token = Column(Text, nullable=True)
    is_active = Column(Boolean, default=False)
    last_tested_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="installations")


class StoreSettings(Base):
    __tablename__ = "store_settings"

    id = Column(Integer, primary_key=True, index=True)
    store_id = Column(Integer, ForeignKey("stores.id"), nullable=False, unique=True)

    weraha_enabled = Column(Boolean, default=False)
    weraha_account_reference = Column(String(100), nullable=True)

    whatsapp_enabled = Column(Boolean, default=False)
    whatsapp_phone_number_id = Column(String(100), nullable=True)
    whatsapp_business_account_id = Column(String(100), nullable=True)

    template_in_transit = Column(String(100), nullable=True)
    template_delivered = Column(String(100), nullable=True)

    onboarding_status = Column(String(50), default="pending")
    test_message_status = Column(String(50), nullable=True)
    last_onboarding_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="settings")
