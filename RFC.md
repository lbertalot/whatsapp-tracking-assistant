RFC v2 — MVP Técnico (Paraguay + Weraha + Meta API)
1. Objetivo

Sistema que:

procesa órdenes
consulta estados logísticos (Weraha)
envía notificaciones WhatsApp
expone visibilidad total al merchant
2. Arquitectura
[Order Source]
        ↓
[FastAPI API]
        ↓
[PostgreSQL]
        ↓
[Polling Worker]
        ↓
[Weraha Adapter]
        ↓
[State Mapper]
        ↓
[Notification Engine]
        ↓
[WhatsApp Service]
3. Componentes
3.1 Ingesta de órdenes
webhook o carga manual
3.2 Phone normalization
phonenumbers
formato E.164
3.3 Polling Worker
cron
frecuencia adaptativa
3.4 Weraha Adapter
consulta estado
devuelve estado raw
3.5 State Mapper
raw → internal:
in_transit
delivered
3.6 Notification Engine
lógica de eventos
evita duplicados
controla estado
3.7 WhatsApp Service
Meta Cloud API
4. Out of scope técnico
no CRM
no chatbot
no múltiples couriers
no múltiples países
no analytics avanzados
5. Modelo de tenancy e instalación
Tablas mínimas:

stores
store_installations
store_settings
store_users

Objetivo:

permitir operación multi-merchant desde el MVP
aislar datos por tienda
sostener panel vendible para múltiples merchants

Modelo sugerido:

CREATE TABLE stores (
    id SERIAL PRIMARY KEY,
    external_store_id VARCHAR(100) UNIQUE,
    name VARCHAR(150) NOT NULL,
    country VARCHAR(50) DEFAULT 'Paraguay',
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE store_installations (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    order_source_type VARCHAR(50) NOT NULL,
    installed_at TIMESTAMP,
    is_active BOOLEAN DEFAULT FALSE,
    last_tested_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE store_settings (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL UNIQUE REFERENCES stores(id),
    weraha_enabled BOOLEAN DEFAULT FALSE,
    weraha_account_reference VARCHAR(100),
    whatsapp_enabled BOOLEAN DEFAULT FALSE,
    whatsapp_phone_number_id VARCHAR(100),
    whatsapp_business_account_id VARCHAR(100),
    template_in_transit VARCHAR(100),
    template_delivered VARCHAR(100),
    onboarding_status VARCHAR(50) DEFAULT 'pending',
    test_message_status VARCHAR(50),
    last_onboarding_error TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

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
6. Modelo de datos (extendido)
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    store_id INTEGER NOT NULL REFERENCES stores(id),
    external_id VARCHAR(100),
    normalized_phone VARCHAR(20),
    tracking_number VARCHAR(100),

    current_status VARCHAR(50),

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
7. Historial de notificaciones e idempotencia
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

Reglas:

idempotency_key = store_id:order_id:event_type
no enviar una notificación final exitosa dos veces para el mismo order_id + event_type
los retries se registran en notification_attempts
los campos last_message_* de orders reflejan el último intento visible al merchant
8. Autenticación y autorización del merchant
El panel es multi-merchant desde el MVP.

Reglas:

cada usuario pertenece a una sola tienda
toda consulta del panel se filtra por store_id
un merchant solo puede ver órdenes, errores y configuraciones de su propia tienda

Endpoints mínimos:

POST /auth/login
POST /auth/logout
GET /me
GET /orders
9. NUEVO — Panel de visibilidad (CRÍTICO)
Endpoint:

GET /orders

Devuelve:
[
  {
    "order_id": "123",
    "store_id": "10",
    "status": "in_transit",
    "notification_status": "sent",
    "last_message_type": "in_transit",
    "last_template_name": "shipping_in_transit_v1",
    "last_message_preview": "Tu pedido #123 ya está en camino",
    "last_notification_at": "2026-01-01",
    "error": null
  }
]

Query params mínimos:

status
notification_status
page
page_size

Reglas:

la respuesta siempre está scopeada por store_id del usuario autenticado
el panel debe permitir listar órdenes y su última trazabilidad visible
10. Flujo mínimo de activación
1. conectar fuente de órdenes
2. configurar acceso a Weraha
3. configurar canal WhatsApp y templates
4. validar envío de prueba
5. activar procesamiento

Objetivo:

tiempo a primera notificación < 1 día en tiendas correctamente configuradas
11. Prerequisitos de WhatsApp
Antes de activar una tienda en producción deben cumplirse:

canal WhatsApp habilitado
templates aprobados para in_transit y delivered
número o identidad operativa correctamente asociada a la tienda o a la plataforma
consentimiento operativo mínimo del merchant para uso del canal
mensaje de prueba validado exitosamente
12. Criterios de elegibilidad de órdenes
Una orden entra al flujo del worker si:

pertenece a una store activa
tiene tracking_number
tiene teléfono normalizable o puede ser marcada como invalid_phone
la tienda completó onboarding_status = active

Estados operativos sugeridos:

pending_tracking
ready_for_polling
in_transit
delivered
notification_failed
invalid_phone
13. Logs obligatorios
orden recibida
estado actualizado
notificación enviada
error
14. Retry strategy
1 retry automático
luego fail
15. Métricas observables
tiempo a primera notificación = first_notification_at - created_at
% órdenes notificadas = órdenes con first_notification_at / órdenes elegibles
% teléfonos inválidos
% errores WhatsApp
% órdenes con tracking tardío
16. Validación de piloto
Estas métricas no se obtienen automáticamente en el MVP y se validan por relevamiento manual:

reducción de consultas WISMO
feedback merchant
uso y percepción de valor del panel
17. Operación mínima y observabilidad
Endpoints:

GET /health
GET /ready

Se debe exponer o registrar como mínimo:

última corrida exitosa del worker
cantidad de órdenes procesadas
errores de Weraha
errores de WhatsApp
tiempo desde último polling exitoso
18. Casos borde
Teléfono inválido
no envía
visible en panel
Tracking tardío
envío retroactivo
Error WhatsApp
retry
log
19. Seguridad
env vars
token webhook
aislamiento por store_id
passwords almacenados como hash
20. Definición de Done

✔️ órdenes procesadas
✔️ tracking funcionando
✔️ notificaciones enviadas
✔️ panel visible
✔️ errores trazables
✔️ acceso aislado por tienda
✔️ onboarding persistido por tienda