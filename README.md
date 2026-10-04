# WhatsApp Tracking Assistant

[![Lint & Code Quality](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/01-lint-and-format.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/01-lint-and-format.yml)
[![Tests & Coverage](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/02-tests.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/02-tests.yml)
[![Security Scanning](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/03-security.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/03-security.yml)
[![Docker Build](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/04-docker-build.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/04-docker-build.yml)

**MVP** de notificaciones automáticas post-compra por WhatsApp para tiendas online en Latinoamérica.

Conecta tu tienda Tiendanube, recibe webhooks de órdenes y envía mensajes automatizados de WhatsApp cuando el estado de envío cambia. Incluye un panel web para visualizar órdenes y configurar notificaciones.

## ¿Qué hace?

- 🔗 **Integración con Tiendanube**: OAuth seguro para conectar tu tienda
- 📦 **Seguimiento de órdenes**: Sincronización automática del estado de envíos
- 💬 **Notificaciones WhatsApp**: Envío de mensajes automáticos vía Meta Cloud API
- 📊 **Panel web**: Visualización de órdenes y trazabilidad de notificaciones
- ⚙️ **Configuración por tienda**: Plantillas, idioma y tokens personalizables

## Stack técnico

- **Backend**: FastAPI (Python 3.12+)
- **Base de datos**: PostgreSQL
- **ORM**: SQLAlchemy + Alembic (migraciones)
- **UI**: Jinja2 templates (integrado al backend)
- **WhatsApp**: Meta Cloud API
- **Tests**: pytest

## Requisitos previos

- Python 3.12+
- PostgreSQL
- Docker y Docker Compose (opcional, recomendado)
- Cuenta de [Tiendanube](https://www.tiendanube.com/)
- Cuenta Business de WhatsApp con Meta Cloud API

## Instalación y ejecución

### Opción A: Docker (recomendado)

```bash
# 1. Clonar el repositorio
git clone https://github.com/lbertalot/whatsapp-tracking-assistant.git
cd whatsapp-tracking-assistant

# 2. Configurar variables de entorno
cp .env.docker.example .env.docker
# Editar .env.docker con tus credenciales

# 3. Iniciar servicios
docker compose up --build

# 4. Crear datos de demostración (opcional)
docker compose run --rm web python scripts/seed_demo_data.py
```

La aplicación estará disponible en `http://localhost:8000`

### Opción B: Entorno virtual Python

```bash
# 1. Clonar el repositorio
git clone https://github.com/lbertalot/whatsapp-tracking-assistant.git
cd whatsapp-tracking-assistant

# 2. Crear entorno virtual
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 5. Crear base de datos
createdb wta_dev

# 6. Aplicar migraciones
alembic upgrade head

# 7. Iniciar aplicación
uvicorn backend.app.main:app --reload
```

La aplicación estará disponible en `http://localhost:8000`

## Configuración

Todas las credenciales y configuraciones se manejan mediante variables de entorno. Revisa `.env.example` para ver todas las opciones disponibles:

- **Database**: `DATABASE_URL`
- **Security**: `SECRET_KEY`, `ACCESS_TOKEN_EXPIRE_MINUTES`
- **WhatsApp**: `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `META_APP_SECRET`
- **Tiendanube**: `TIENDANUBE_APP_ID`, `TIENDANUBE_CLIENT_SECRET`
- **App**: `APP_BASE_URL`, `APP_ENV`, `LOG_LEVEL`

Ver documentación completa en [`docs/WHATSAPP_META.md`](docs/WHATSAPP_META.md) para configurar Meta Cloud API.

## Estructura del proyecto

```
backend/app/
  api/          # Endpoints FastAPI (auth, orders, webhooks, settings)
  core/         # Configuración, seguridad, dependencias
  db/           # Sesión de base de datos
  models/       # Modelos SQLAlchemy (Store, Order, Notification, User)
  schemas/      # Schemas Pydantic para validación
  services/     # Lógica de negocio (Tiendanube, WhatsApp, notificaciones)
  workers/      # Worker de sincronización periódica
  templates/    # Templates HTML (Jinja2)
  static/       # Archivos estáticos (CSS, JS)

docs/           # Documentación técnica
tests/          # Suite de tests con pytest
scripts/        # Scripts de utilidad (seed, demo)
```

## Uso

1. **Registro**: Accede a `/register` para crear una cuenta
2. **Vincular Tiendanube**: Completa el proceso de OAuth desde `/onboarding`
3. **Configurar WhatsApp**: Ingresa tus credenciales de Meta en `/settings`
4. **Panel**: Visualiza órdenes y notificaciones en `/panel`

## Tests

```bash
# Ejecutar todos los tests
pytest

# Con cobertura
pytest --cov=backend/app --cov-report=html

# Tests específicos
pytest tests/test_api/
pytest tests/test_services/
```

## Documentación adicional

- [`docs/SPEC.md`](docs/SPEC.md) — Especificación técnica completa
- [`docs/DOCKER.md`](docs/DOCKER.md) — Detalles de ejecución con Docker
- [`docs/WHATSAPP_META.md`](docs/WHATSAPP_META.md) — Configuración de Meta Cloud API
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — Guía para contribuir
- [`SECURITY.md`](SECURITY.md) — Política de seguridad

## Limitaciones del MVP

Este es un **MVP (Producto Mínimo Viable)**:

- Solo soporta Tiendanube como plataforma de ecommerce
- Plantillas de WhatsApp limitadas
- Sin analytics avanzados
- No es un CRM completo ni un chatbot
- Funcionalidad básica de notificaciones post-compra

## Licencia

[MIT License](LICENSE)

## Contribuciones

Las contribuciones son bienvenidas. Por favor revisa [`CONTRIBUTING.md`](CONTRIBUTING.md) para más detalles sobre el flujo de trabajo y las convenciones del proyecto.

---

**Nota**: Este proyecto es un MVP de demostración. Para uso en producción se recomienda revisar las configuraciones de seguridad, escalabilidad y cumplimiento normativo según tu región.
