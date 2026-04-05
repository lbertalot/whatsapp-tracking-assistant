-- WhatsApp Tracking Assistant — Schema snapshot (reference only)
-- Authoritative schema: Alembic migrations under alembic/versions/
-- See ADR-006: ecommerce as source of truth (no courier adapter in core)

-- 1. Stores (tenancy)
CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    external_store_id VARCHAR(100) UNIQUE,
    name VARCHAR(150) NOT NULL,
    country VARCHAR(50) DEFAULT '',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 2. Store installations (order source)
CREATE TABLE store_installations (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    order_source_type VARCHAR(50) NOT NULL,
    installed_at TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE,
    last_tested_at TIMESTAMP,
    access_token TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 3. Store settings (ecommerce sync, WhatsApp, onboarding)
CREATE TABLE store_settings (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL UNIQUE REFERENCES stores(id),
    ecommerce_sync_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    default_phone_region VARCHAR(5),
    whatsapp_enabled BOOLEAN DEFAULT FALSE,
    whatsapp_include_body_params BOOLEAN NOT NULL DEFAULT TRUE,
    whatsapp_phone_number_id VARCHAR(100),
    whatsapp_business_account_id VARCHAR(100),
    whatsapp_access_token TEXT,
    whatsapp_template_language VARCHAR(10),
    template_in_transit VARCHAR(100),
    template_delivered VARCHAR(100),
    onboarding_status VARCHAR(50) DEFAULT 'pending',
    test_message_status VARCHAR(50),
    last_onboarding_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. Store users (panel auth)
CREATE TABLE store_users (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    email VARCHAR(150) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) DEFAULT 'admin',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 5. Orders
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    external_id VARCHAR(100),
    customer_name VARCHAR(200),
    raw_phone VARCHAR(50),
    normalized_phone VARCHAR(20),
    tracking_number VARCHAR(100),
    tracking_url VARCHAR(500),
    current_status VARCHAR(50),
    platform_status_raw VARCHAR(100),
    last_status_source VARCHAR(20),
    notified_in_transit BOOLEAN DEFAULT FALSE,
    notified_delivered BOOLEAN DEFAULT FALSE,
    notification_status VARCHAR(50),
    notification_error TEXT,
    last_message_type VARCHAR(50),
    last_template_name VARCHAR(100),
    last_message_preview TEXT,
    first_notification_at TIMESTAMP,
    last_notification_at TIMESTAMP,
    invalid_phone BOOLEAN DEFAULT FALSE,
    last_checked_at TIMESTAMP,
    last_status_change_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 6. Notification attempts (idempotency + traceability)
CREATE TABLE notification_attempts (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    order_id INTEGER NOT NULL REFERENCES orders(id),
    event_type VARCHAR(50) NOT NULL,
    idempotency_key VARCHAR(255) NOT NULL UNIQUE,
    template_name VARCHAR(100),
    status VARCHAR(50) NOT NULL,
    provider_message_id VARCHAR(150),
    error_code VARCHAR(100),
    error_message TEXT,
    attempt_number INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orders_store_id ON orders(store_id);
CREATE INDEX idx_orders_current_status ON orders(current_status);
CREATE INDEX idx_orders_store_status ON orders(store_id, current_status);
CREATE INDEX idx_notification_attempts_order ON notification_attempts(order_id);
CREATE INDEX idx_notification_attempts_store ON notification_attempts(store_id);
