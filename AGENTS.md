# AGENTS.md — Instrucciones para agentes AI

## Contexto del proyecto

Este es un MVP de notificaciones post-compra por WhatsApp para merchants en Paraguay.
El sistema recibe órdenes, consulta el estado logístico en Weraha, y envía notificaciones proactivas por WhatsApp cuando el estado cambia.

Antes de escribir código, leé estos documentos:

- `docs/PRD.md` — qué se construye y por qué
- `docs/RFC.md` — cómo se construye técnicamente
- `docs/ADR.md` — qué decisiones de arquitectura se tomaron y por qué
- `docs/MILESTONES.md` — plan por milestones, dependencias y criterios de aceptación

## Stack

- **Backend**: FastAPI (Python 3.11+)
- **ORM**: SQLAlchemy + Alembic
- **DB**: PostgreSQL
- **UI**: Jinja2 templates integrados al backend (NO Next.js, NO React)
- **Infra**: Heroku (web + worker + scheduler + postgres) y/o Docker local (`docs/DOCKER.md`)
- **WhatsApp**: Meta Cloud API
- **Logística**: Weraha API
- **Teléfonos**: phonenumbers (E.164)
- **Auth**: bcrypt + JWT simple
- **Tests**: pytest

## Estructura del proyecto

```
backend/
  app/
    __init__.py
    main.py               # FastAPI app entry point
    core/
      __init__.py
      config.py            # Settings desde env vars
      security.py          # Hash, JWT, auth dependencies
      dependencies.py      # Shared FastAPI dependencies
    api/
      __init__.py
      auth.py              # POST /auth/login, /auth/logout, GET /me
      orders.py            # GET /orders (panel), POST /webhooks/orders
      health.py            # GET /health, GET /ready
      integrations.py      # OAuth Tiendanube (install/callback) — extender con MS-ONB01
      settings.py          # GET/PUT /api/settings, GET /panel/stats
      webhooks_tn.py       # POST /webhooks/tiendanube
      ui.py                # Rutas que renderizan templates HTML
    models/
      __init__.py
      store.py             # Store, StoreInstallation, StoreSettings
      user.py              # StoreUser
      order.py             # Order
      notification.py      # NotificationAttempt
    services/
      __init__.py
      weraha.py            # Weraha adapter
      whatsapp.py          # WhatsApp Meta Cloud API service
      notification.py      # Notification engine con idempotencia
      phone.py             # Normalización de teléfonos
      state_mapper.py      # Mapeo raw → internal status
      tiendanube.py        # TiendanubeService (OAuth, API store, webhooks)
    workers/
      __init__.py
      polling.py           # Polling worker principal
    db/
      __init__.py
      session.py           # Engine, SessionLocal, get_db
      base.py              # Base declarativa
    schemas/
      __init__.py
      auth.py              # Login request/response
      order.py             # Order response, filtros
      store.py             # Store schemas
    templates/
      base.html
      login.html
      orders.html
      settings.html        # Config templates TN (MS previos); onboarding TN en MS-ONB01
    static/
      css/
        style.css
      js/
        app.js

docs/
  PRD.md
  RFC.md
  ADR.md
  MILESTONES.md
  DOCKER.md

tests/
  __init__.py
  conftest.py
  test_api/
    __init__.py
    test_auth.py
    test_orders.py
    test_health.py
  test_services/
    __init__.py
    test_weraha.py
    test_whatsapp.py
    test_notification.py
    test_phone.py
  test_workers/
    __init__.py
    test_polling.py

.env.example
requirements.txt
Procfile
.python-version
README.md
AGENTS.md
```

## Fases de desarrollo

### Fase 1 — Fundación
- FastAPI app base con config y health
- Modelos SQLAlchemy: stores, store_users, store_settings, store_installations, orders, notification_attempts
- Alembic init + migración inicial
- Auth simple (login, logout, me)
- Endpoint GET /orders scopeado por store_id
- Endpoint POST /webhooks/orders
- Templates Jinja2: login + lista de órdenes
- CSS mínimo vendible

### Fase 2 — Worker + Weraha
- Polling worker
- Weraha adapter (primero mock, luego real)
- State mapper
- Actualización de estados en DB
- Visibilidad de estados en panel

### Fase 3 — WhatsApp + Notificaciones
- WhatsApp service (Meta Cloud API)
- Notification engine con idempotencia
- Registro de intentos en notification_attempts
- Retry strategy (1 retry, luego fail)
- Trazabilidad visible en panel
- Configuración persistida por tienda

### Fase 4 — Endurecimiento
- Mejoras UX/UI del panel
- Health checks y observabilidad
- Métricas de piloto
- Refinamiento de onboarding

### Milestone MS-ONB01 — Onboarding Tiendanube (vinculación obligatoria en panel)

**Dependencias previas:** MS-B03 (JWT), MS-I01 (OAuth TN base), MS-F02 (panel).  
**Especificación completa:** `docs/MILESTONES.md` → sección **MS-ONB01**.

**Objetivo:** El merchant que **ya inició sesión** debe **vincular su Tiendanube** al **mismo** `Store` que su JWT (`store_id`); no crear tiendas huérfanas por callback OAuth.

#### Backend (orden sugerido)

1. **Token exchange TN:** Confirmar en documentación oficial si `POST .../apps/authorize/token` usa JSON o `application/x-www-form-urlencoded`; alinear `TiendanubeService.exchange_code()` (hoy usa `data=` form).
2. **`state` OAuth:** JWT firmado con `SECRET_KEY`, payload `{ store_id, exp, purpose: "tn_oauth" }`, TTL corto (≤ 15 min).
3. **Endpoint autenticado** `GET /api/integrations/tiendanube/authorize` (o equivalente): requiere `Authorization: Bearer`; responde **302** a la URL de autorización TN **con `state`** en query (validar nombre del parámetro en TN).
4. **Callback** `GET /integrations/tiendanube/callback`: leer `code` + `state`; validar JWT; resolver `store_id`; intercambiar código; persistir `access_token` en `StoreInstallation` de **ese** `store`; `Store.external_store_id = str(user_id)` TN; opcional `fetch_store_info` para nombre; actualizar `StoreSettings.onboarding_status` según política acordada.
5. **Conflictos:** Si `external_store_id` ya existe y ≠ `user_id` del token → **409** + mensaje claro (o documentar flujo desvincular fuera de MVP).
6. **`GET /api/onboarding/status`** (JWT): JSON con `needs_tiendanube`, `tiendanube_user_id`, `installation_active`, `onboarding_status`, `store_name` para gating en UI.
7. **Opcional en ONB01:** Tras éxito, llamar `register_webhooks` (si no queda solo en MS-I02).
8. **Logs:** nunca loguear `access_token` completo.

#### Frontend (Jinja + JS)

1. **`GET /onboarding`** (o `/onboarding/tiendanube`): copy claro, CTA “Conectar con Tiendanube” → redirect al authorize autenticado (token en header no aplica a redirect del browser: usar patrón **URL firmada de un solo uso**, **cookie http-only**, o **query token de corta vida** según decisión segura documentada en ADR).
2. **Guard:** En `/panel` y `/settings`, si `needs_tiendanube` → redirigir a `/onboarding` (o modal bloqueante).
3. **Post-callback:** Páginas o query `success` / `error` con mensajes accionables en español.

#### Tests (TDD)

- `test_onboarding_status_unauthenticated` → 401  
- `test_onboarding_status_needs_tn` / `test_onboarding_status_linked`  
- `test_tn_authorize_requires_auth` → 401  
- `test_tn_authorize_redirect_includes_state`  
- `test_tn_callback_valid_state_links_store`  
- `test_tn_callback_invalid_state` / expirado → 400  
- `test_tn_callback_mismatched_store` → 404  
- `test_token_exchange_json_body` (si aplica contrato JSON)

#### E2E milestone

Login (fixture) → status → authorize (mock) → callback simulado → linked → `/panel` sin bloqueo.

#### Notas

- Revisar **scopes** OAuth TN: `write_products` puede ser insuficiente para órdenes/webhooks (MS-I02).
- Callback URL en el portal de la app TN debe coincidir con `APP_BASE_URL` + ruta de callback.

## Reglas para agentes

### Generales
- NO crear CRM, chatbot, analytics avanzados ni features fuera del MVP
- NO introducir Next.js, React ni frontend separado
- NO crear microservicios: esto es un monolito
- NO agregar dependencias sin justificación clara
- Responder siempre en español al usuario

### Código
- Type hints en funciones públicas
- Async para IO (DB, Weraha, WhatsApp)
- Toda query filtra por store_id
- Passwords hasheados con bcrypt
- Config desde env vars via Pydantic Settings
- Logs estructurados para eventos clave

### Base de datos
- Migraciones con Alembic
- Nunca DROP ni ALTER destructivo sin confirmación
- FK obligatoria a stores en tablas de negocio

### Tests
- pytest con fixtures de store, user, orders
- Mock de APIs externas (Weraha, WhatsApp)
- No testear código de terceros

### Git
- Commits en inglés, concisos
- Un commit por cambio lógico
- No commitear .env, secrets ni credenciales
