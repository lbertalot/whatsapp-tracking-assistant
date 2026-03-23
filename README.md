# WhatsApp Tracking Assistant

Sistema MVP de notificaciones post-compra por WhatsApp para merchants en Paraguay.

Reduce consultas WISMO automatizando avisos de estado de envío y dando visibilidad completa al merchant sobre cada notificación.

## Stack

- **Backend**: FastAPI (Python 3.11+)
- **Base de datos**: PostgreSQL
- **UI**: Jinja2 templates integrados al backend
- **Infraestructura**: Heroku / Docker local
- **WhatsApp**: Meta Cloud API
- **Logística**: Weraha API

## Setup local

### Opción A — Docker (recomendado, paridad con Heroku)

```bash
cp .env.docker.example .env.docker   # opcional
docker compose up --build
# Datos demo (tienda + órdenes TN-100x):
docker compose run --rm web python scripts/seed_demo_data.py
# Por defecto el seed usa SEED_TN_LINK_MODE=oauth_ready (panel pide vincular TN real).
# Panel demo sin OAuth: SEED_TN_LINK_MODE=demo docker compose run --rm web python scripts/seed_demo_data.py
```

Detalle: [docs/DOCKER.md](docs/DOCKER.md)

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
- [DOCKER.md](docs/DOCKER.md) — Ejecución local con Docker (paridad Heroku)

## Despliegue (Heroku)

```bash
heroku create wta-app
heroku addons:create heroku-postgresql:mini
git push heroku main
heroku ps:scale web=1 worker=1
```
