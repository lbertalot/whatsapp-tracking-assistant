# WhatsApp Cloud API (Meta) — configuración WTA

Guía operativa alineada a **MS-I06**, **MS-I07** e **MS-I08** (`docs/MILESTONES.md`) y **ADR-005** (`docs/ADR.md`).

## 1. Variables de entorno (app / Docker)

| Variable | Uso |
|----------|-----|
| `WHATSAPP_API_URL` | Base Graph API (ej. `https://graph.facebook.com/v25.0`) |
| `WHATSAPP_ACCESS_TOKEN` | Token global (solo si `WHATSAPP_ALLOW_GLOBAL_FALLBACK=true`) |
| `WHATSAPP_PHONE_NUMBER_ID` | ID de número global (mismo caso) |
| `WHATSAPP_ALLOW_GLOBAL_FALLBACK` | `true`: tiendas sin token propio usan el global. `false`: multi-tenant estricto (recomendado en prod). |
| `META_APP_SECRET` | Firma del webhook `POST /webhooks/whatsapp` |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | Token arbitrario; debe coincidir con el configurado en el portal de Meta (suscripción webhook) |
| `APP_BASE_URL` | Origen público HTTPS (callback webhook: `{APP_BASE_URL}/webhooks/whatsapp`) |

## 2. Credenciales por tienda (MS-I08)

En el panel web: **Configuración** → sección **WhatsApp (Meta Cloud API)** (`/settings`), o vía API `PUT /api/settings` (autenticado):

- `whatsapp_phone_number_id`
- `whatsapp_access_token` (no se devuelve en `GET`; solo `whatsapp_token_configured`)
- `whatsapp_template_language` (ej. `es`, `es_AR` según plantilla aprobada en Business Manager)

`GET /api/settings` **nunca** incluye el token en claro.

## 3. Webhook en Meta

1. App Meta → Webhooks → suscribir producto **whatsapp_business_account** (campos según necesidad; mínimo útil: eventos que envían `statuses`).
2. URL de callback: `https://<tu-dominio>/webhooks/whatsapp`.
3. **Verify token** = valor de `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
4. **App Secret** = `META_APP_SECRET` (firma `X-Hub-Signature-256`).

En local, exponer HTTPS con **ngrok** (u otro túnel) y usar esa URL en Meta.

## 4. Plantillas y parámetros (MS-I06)

El worker envía `template.components` con variables (`order_id`) cuando la tienda tiene **`whatsapp_include_body_params=true`** (por defecto) y las notificaciones están habilitadas con **`whatsapp_enabled=true`**. Si la plantilla en Meta **no declara variables** en el cuerpo, desactivá **Incluir variables del pedido** en `/settings` (o `PUT /api/settings` con `whatsapp_include_body_params: false`) para no enviar `components` y evitar rechazos de la API.

El nombre de plantilla por evento puede sobreescribirse con `template_in_transit` / `template_delivered` en `store_settings`.

## 5. Rate limit (429)

Si Meta devuelve `Retry-After`, el motor de notificaciones espera (tope 120 s) antes del siguiente intento dentro del mismo ciclo de reintentos.

## 6. Homologación y go-live

- Checklist **paso a paso** (Meta, plantillas, webhook, worker): **`docs/META_GO_LIVE_CHECKLIST.md`**.
- Checklist amplio de producto: **MS-H02** (`MILESTONES.md`).

No sustituye revisión legal / App Review de Meta.
