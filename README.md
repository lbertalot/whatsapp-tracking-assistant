# WhatsApp Tracking Assistant

[![Lint & Code Quality](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/01-lint-and-format.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/01-lint-and-format.yml)
[![Tests & Coverage](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/02-tests.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/02-tests.yml)
[![Security Scanning](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/03-security.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/03-security.yml)
[![Docker Build](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/04-docker-build.yml/badge.svg)](https://github.com/lbertalot/whatsapp-tracking-assistant/actions/workflows/04-docker-build.yml)

Sistema MVP de notificaciones post-compra por WhatsApp para merchants en **Latinoamérica** (fuente de verdad: **tienda ecommerce**, MVP: **Tiendanube**).

Reduce consultas WISMO automatizando avisos de estado de envío y dando visibilidad completa al merchant sobre cada notificación.

## Stack

- **Backend**: FastAPI (Python 3.12+)
- **Base de datos**: PostgreSQL
- **UI**: Jinja2 templates integrados al backend
- **Infraestructura**: Heroku / Docker local
- **WhatsApp**: Meta Cloud API
- **Estado de envío**: datos de la plataforma de tienda (Tiendanube API + webhooks; sync periódico)

## Setup local

### Opción A — Docker (recomendado, paridad con Heroku)

```bash
cp .env.docker.example .env.docker   # opcional
docker compose up --build
# Datos demo (tienda + órdenes TN-100x):
docker compose run --rm web python scripts/seed_demo_data.py
# Por defecto el seed usa SEED_TN_LINK_MODE=oauth_ready (panel pide vincular TN real).
# Panel demo sin OAuth: SEED_TN_LINK_MODE=demo docker compose run --rm web python scripts/seed_demo_data.py
# Cuenta nueva sin seed: abrí http://localhost:8000/register (MS-ONB02).
```

Detalle: [docs/DOCKER.md](docs/DOCKER.md) · WhatsApp/Meta: [docs/WHATSAPP_META.md](docs/WHATSAPP_META.md)

### Opción B — Python en la máquina

```bash
# 1. Clonar
git clone <repo-url>
cd WhatsApp-Tracking-Assistant

# 2. Entorno virtual
python -m venv .venv
source .venv/bin/activate

# 3. Dependencias
pip install -r requirements.txt

# 4. Variables de entorno
cp .env.example .env
# Editar .env con tus valores

# 5. Base de datos
createdb wta_dev
alembic upgrade head

# 6. Correr
uvicorn backend.app.main:app --reload
```

## Estructura

```
backend/app/
  api/          # Endpoints FastAPI
  core/         # Config, security, dependencies
  db/           # DB session, schema
  models/       # SQLAlchemy models
  schemas/      # Pydantic schemas
  services/     # Tiendanube, WhatsApp, notificaciones, phone, estado ecommerce
  workers/      # Polling worker
  templates/    # Jinja2 HTML
  static/       # CSS, JS

docs/           # SPEC.md (producto + RFC + ADRs)
tests/          # pytest
```

## Documentación

- [SPEC.md](docs/SPEC.md) — Producto, diseño técnico (RFC) y decisiones (ADRs)
- [MILESTONES.md](docs/MILESTONES.md) — Hitos, estado de implementación y tests
- [PILOT_READINESS.md](docs/PILOT_READINESS.md) — Piloto tienda real (TN + WhatsApp) y DoD
- [WHATSAPP_META.md](docs/WHATSAPP_META.md) — Meta Cloud API, env vars y panel
- [META_GO_LIVE_CHECKLIST.md](docs/META_GO_LIVE_CHECKLIST.md) — Checklist antes de producción (Meta)
- [DOCKER.md](docs/DOCKER.md) — Ejecución local con Docker (paridad Heroku)
- [CONTRIBUTING.md](CONTRIBUTING.md) — CI/CD, pre-commit, convenciones

> **CI:** los badges apuntan a `github.com/lbertalot/whatsapp-tracking-assistant`. Si tu fork u org es otro, actualizá las URLs en esta cabecera.

### Rutas HTTP principales (FastAPI)

| Área | Rutas (públicas salvo nota) |
|------|-----------------------------|
| Salud | `GET /health`, `GET /ready`, `GET /metrics` (sin JWT; **métricas globales**, ver MS-I05) |
| Auth / usuario | `POST /auth/login`, `POST /auth/register`, `GET /me` (JWT en órdenes/panel/settings) |
| Panel datos | `GET /orders`, `GET /panel/stats` (JWT) |
| Config tienda | `GET/PUT /api/settings` (JWT) |
| TN OAuth | `GET /integrations/tiendanube/install`, `GET /integrations/tiendanube/callback`; panel: `GET /api/integrations/tiendanube/install-url` (JWT) |
| Onboarding API | `GET /api/onboarding/status` (JWT) |
| Webhooks | `POST /webhooks/tiendanube` (HMAC TN), `POST /webhooks/orders` (firma app), `GET/POST /webhooks/whatsapp` (Meta) |
| UI (HTML) | `/`, `/login`, `/register`, `/panel`, `/onboarding`, `/settings`, `/ayuda/conectar-tiendanube`, `/privacidad` |

## Despliegue (Heroku)

Alineado con [Getting Started on Heroku with Python](https://devcenter.heroku.com/articles/getting-started-with-python): `requirements.txt`, `Procfile`, `.python-version`, Postgres y [Release Phase](https://devcenter.heroku.com/articles/release-phase) para migraciones.

```bash
heroku create wta-app
# Plan mínimo vigente (ver: heroku addons:plans heroku-postgresql)
heroku addons:create heroku-postgresql:essential-0
git push heroku main
heroku ps:scale web=1 worker=1
```

- **`release`** en el `Procfile` ejecuta `alembic upgrade head` en cada deploy (antes de que los dynos nuevos reciban tráfico). Revisá en los logs del build la sección *Running release command*.
- **Python:** la versión se fija con **`.python-version`** (hoy `3.12`); el buildpack ya no usa `runtime.txt`.

Si el release falló o necesitás aplicar migraciones a mano:

```bash
heroku run alembic upgrade head
```

Si no tenés el remoto `heroku` en este clon, usá `-a nombre-de-tu-app` (ej. `heroku run alembic upgrade head -a wta-dev`).

**Webhooks (Tiendanube, Meta):** los dynos **Eco** pueden dormir tras inactividad; el primer request puede tardar. Para entornos donde los callbacks deben ser estables, valorá **`web`** en **Basic** o superior ([Dyno sleeping](https://devcenter.heroku.com/articles/dyno-sleeping)).
