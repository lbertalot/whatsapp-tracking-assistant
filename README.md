# WhatsApp Tracking Assistant

Sistema MVP de notificaciones post-compra por WhatsApp para merchants en Paraguay.

Reduce consultas WISMO automatizando avisos de estado de envío y dando visibilidad completa al merchant sobre cada notificación.

## Stack

- **Backend**: FastAPI (Python 3.11+)
- **Base de datos**: PostgreSQL
- **UI**: Jinja2 templates integrados al backend
- **Infraestructura**: Heroku
- **WhatsApp**: Meta Cloud API
- **Logística**: Weraha API

## Setup local

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
psql wta_dev < backend/app/db/schema.sql

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
  services/     # Weraha, WhatsApp, notificaciones, phone
  workers/      # Polling worker
  templates/    # Jinja2 HTML
  static/       # CSS, JS

docs/           # PRD, RFC, ADR
tests/          # pytest
```

## Documentación

- [PRD.md](docs/PRD.md) — Producto
- [RFC.md](docs/RFC.md) — Diseño técnico
- [ADR.md](docs/ADR.md) — Decisiones de arquitectura

## Despliegue (Heroku)

```bash
heroku create wta-app
heroku addons:create heroku-postgresql:mini
git push heroku main
heroku ps:scale web=1 worker=1
```
