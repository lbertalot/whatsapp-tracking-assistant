# Docker (paridad local con Heroku)

El `Procfile` de Heroku define **web** (`uvicorn`) y **worker** (`python -m backend.app.workers.polling`).  
`docker-compose.yml` levanta los mismos procesos más **PostgreSQL 16**.

## Requisitos

- Docker Engine + Docker Compose v2 (Mac: Docker Desktop, Linux: `docker compose`).
- Puerto **8000** libre (o cambiá el mapeo en `docker-compose.yml`).

## Arranque rápido

```bash
# Opcional: variables extra (WhatsApp, etc.)
cp .env.docker.example .env.docker

# Build + migraciones (Alembic) + web + worker + Postgres
docker compose up --build
```

- API / UI: <http://localhost:8000>
- Salud: <http://localhost:8000/health>
- Login: <http://localhost:8000/login>
- Ayuda (vincular Tiendanube, sin login): <http://localhost:8000/ayuda/conectar-tiendanube>
- Panel: <http://localhost:8000/panel>

### Cambiaste código o plantillas y ves `404` o comportamiento viejo

La imagen **copia el código al hacer build**; `docker compose restart` **no** incorpora archivos nuevos del disco.

```bash
docker compose build web && docker compose up -d web
# Si también tocó lógica compartida con el worker:
docker compose build web worker && docker compose up -d web worker
```

La primera vez que arranca **web**, el script `docker/entrypoint-web.sh` ejecuta `alembic upgrade head` y luego `uvicorn`.

## Datos de demostración (como Heroku)

Regenera la tienda **Tienda Demo Paraguay**, usuario de panel y ~10 órdenes (TN-1001 … TN-1010) con la misma mezcla de estados que en el entorno demo:

```bash
docker compose run --rm web python scripts/seed_demo_data.py
```

Credenciales del usuario demo del seed (definidas por defecto **en el script**; opcionalmente sobreescribibles con `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` solo si hace falta otro email para el wipe o otra contraseña):

- **Email:** `demo@tiendademo.py`
- **Contraseña:** `DemoWTA2026!`

En producción el merchant crea cuenta vía **`/register`** (MS-ONB02); no hace falta poner `SEED_USER_*` en `.env`.

Variables del seed (ver docstring en `scripts/seed_demo_data.py`):

- **`SEED_TN_LINK_MODE`** (default: **`oauth_ready`**): deja `external_store_id` **NULL** y sin token TN → el panel pide **Conectar Tiendanube** (ideal para probar OAuth con una tienda real). No mezcles OAuth real con datos viejos que usaban `demo-paraguay-tn`.
- **`demo`**: comportamiento anterior (panel “ya vinculado” con `external_store_id` ficticio y token placeholder) para enseñar métricas sin OAuth.
- **`SEED_STORE_EXTERNAL_ID`**: opcional; en `demo` por defecto `demo-paraguay-tn`; en `oauth_ready` podés fijar un `user_id` TN conocido (staging).

El seed **borra y recrea** la tienda asociada al usuario demo (mismo email en cada corrida: default del script o el que definas en `SEED_USER_EMAIL`).

## Migraciones solo (sin levantar web)

```bash
docker compose run --rm web alembic upgrade head
```

## Worker más rápido en desarrollo

```bash
cp docker-compose.override.example.yml docker-compose.override.yml
# Ajustá POLL_INTERVAL_SECONDS en el override si querés
docker compose up --build
```

`docker-compose.override.yml` está en `.gitignore` y no debe committearse.

## Variables de entorno

| Origen | Uso |
|--------|-----|
| `docker-compose.yml` | `DATABASE_URL` apunta al servicio `postgres`. |
| `.env.docker` (opcional) | Secretos y integraciones; copiá desde `.env.docker.example`. |
| Entorno del host | Podés exportar `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `SECRET_KEY`, etc., antes de `docker compose up`. |

**Tiendanube en Docker:** el servicio `web` usa `env_file: .env.docker` únicamente. Si tenés `TIENDANUBE_APP_ID` / `TIENDANUBE_CLIENT_SECRET` solo en `.env` del host, el panel mostrará *“Falta configurar Tiendanube en el servidor”*. Copiá esas dos variables a `.env.docker` (y mantené `APP_BASE_URL` acorde a cómo abrís el panel, p. ej. `http://localhost:8000`). Luego `docker compose build web && docker compose up -d web`.

**`APP_BASE_URL` en Docker:** no se toma del `.env` del host para el servicio `web` (evita que una URL de Heroku en el repo local rompa callbacks y enlaces al abrir `http://localhost:8000`). Definila en **`.env.docker`**; para producción en Heroku seguí usando las vars de la plataforma.

`POLL_INTERVAL_SECONDS` debe definirse en `.env.docker` (o en `docker-compose.override.yml` en `worker.environment`, que tiene prioridad). No uses solo el `.env` del host salvo que exportes la variable antes de `docker compose up`, porque Compose no interpola `.env.docker` en la sección `environment:` del YAML.

## Comandos útiles

```bash
# Ver logs
docker compose logs -f web worker

# Shell en el contenedor app
docker compose run --rm web bash

# Tests (dentro del contenedor; requiere DB de test si los configurás)
docker compose run --rm web pytest tests/ -q

# Apagar y conservar datos de Postgres
docker compose down

# Apagar y borrar volumen de Postgres
docker compose down -v
```

## Solución de problemas

- **`GET /ayuda/...` u otra ruta nueva responde `{"detail":"Not Found"}`:** el contenedor sigue con una imagen antigua; hacé **rebuild** del servicio `web` (ver sección arriba).
- **El worker arranca antes que las migraciones:** el `worker` depende de `web` con `condition: service_healthy`; `web` corre Alembic antes de exponer `/health`.
- **Error de conexión a Postgres:** esperá a que el healthcheck de `postgres` esté en verde (`docker compose ps`).
- **Weraha en dev:** sin `WERAHA_API_URL` HTTP real (o URL placeholder `https://mock`), el adapter usa respuesta mock; no confundir con credenciales Meta/WhatsApp.
- **Webhook WhatsApp (Meta):** callback público `GET/POST {APP_BASE_URL}/webhooks/whatsapp`. En local hace falta HTTPS expuesto (p. ej. ngrok) y variables `META_APP_SECRET` + `WHATSAPP_WEBHOOK_VERIFY_TOKEN` en `.env.docker`. Guía: [`docs/WHATSAPP_META.md`](WHATSAPP_META.md); decisión técnica: `docs/ADR.md` (ADR-005).

## Imagen

Un solo **Dockerfile** instala dependencias y sirve para **web** y **worker**; solo cambia el `command` en Compose.
