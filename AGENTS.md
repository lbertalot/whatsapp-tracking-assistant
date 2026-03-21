# AGENTS.md — Instrucciones para agentes AI

## Contexto del proyecto

Este es un MVP de notificaciones post-compra por WhatsApp para merchants en Paraguay.
El sistema recibe órdenes, consulta el estado logístico en Weraha, y envía notificaciones proactivas por WhatsApp cuando el estado cambia.

Antes de escribir código, leé estos documentos:

- `PRD.md` — qué se construye y por qué
- `RFC.md` — cómo se construye técnicamente
- `ADR.md` — qué decisiones de arquitectura se tomaron y por qué

## Stack

- **Backend**: FastAPI (Python 3.11+)
- **ORM**: SQLAlchemy + Alembic
- **DB**: PostgreSQL
- **UI**: Jinja2 templates integrados al backend (NO Next.js, NO React)
- **Infra**: Heroku (web + worker + scheduler + postgres)
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
    static/
      css/
        style.css
      js/
        app.js

docs/
  PRD.md
  RFC.md
  ADR.md

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
runtime.txt
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
