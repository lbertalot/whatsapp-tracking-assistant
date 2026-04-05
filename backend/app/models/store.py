from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.app.db.base import Base


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    external_store_id = Column(String(100), unique=True, nullable=True)
    name = Column(String(150), nullable=False)
    country = Column(String(50), default="")
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

    # Sync order/shipment state from the ecommerce platform API (Tiendanube first; see ADR-006).
    ecommerce_sync_enabled = Column(Boolean, default=True, nullable=False)
    # ISO 3166-1 alpha-2 for phonenumbers.parse when the number has no country code
    # (e.g. PY, AR, MX).
    default_phone_region = Column(String(5), nullable=True)

    whatsapp_enabled = Column(Boolean, default=False)
    # Si False, no se envía `template.components` (plantillas sin variables en el body).
    whatsapp_include_body_params = Column(Boolean, default=True, nullable=False)
    whatsapp_phone_number_id = Column(String(100), nullable=True)
    whatsapp_business_account_id = Column(String(100), nullable=True)
    whatsapp_access_token = Column(Text, nullable=True)
    whatsapp_template_language = Column(String(10), nullable=True)

    template_in_transit = Column(String(100), nullable=True)
    template_delivered = Column(String(100), nullable=True)

    onboarding_status = Column(String(50), default="pending")
    # MS-ONB03: set when first TN orders bulk import finished (success).
    tn_initial_import_completed_at = Column(DateTime, nullable=True)
    test_message_status = Column(String(50), nullable=True)
    last_onboarding_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    store = relationship("Store", back_populates="settings")
