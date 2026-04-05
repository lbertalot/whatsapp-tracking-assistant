# Checklist Meta / WhatsApp — antes de producción (WTA)

Lista operativa para validar el entorno real con **Meta Cloud API** y esta app. Complementa `docs/WHATSAPP_META.md` y **MS-H02** en `MILESTONES.md`. No reemplaza **App Review** ni asesoría legal.

## 1. App y permisos (Meta for Developers)

- [ ] App en modo **Live** (o número de prueba allowlist para staging).
- [ ] Producto **WhatsApp** configurado; **Phone number ID** y **WABA** correctos para el número que usarán los clientes.
- [ ] Token de acceso con permisos para enviar mensajes (`whatsapp_business_messaging` según versión de la API).
- [ ] Plan de **rotación de tokens**: documentar quién renueva el token de larga duración / System User (ver [documentación Meta](https://developers.facebook.com/docs/whatsapp)).

## 2. Plantillas (Business Manager)

- [ ] Plantillas **UTILITY** (o categoría aprobada) para *en tránsito* y *entregado*, en el idioma configurado (`whatsapp_template_language` en `/settings`, ej. `es` vs `es_AR`).
- [ ] Nombres de plantilla coinciden con `template_in_transit` / `template_delivered` (o con los defaults del código).
- [ ] Si el cuerpo de la plantilla **no tiene variables**: en `/settings` desactivar **Incluir variables del pedido** (`whatsapp_include_body_params=false`).
- [ ] Si tiene variables: el body debe alinearse con el orden que envía WTA (`order_id` primero; ver `build_template_body_components`).

## 3. Credenciales en WTA

- [ ] Por tienda: **Notificaciones WhatsApp habilitadas**, Phone number ID, token (si no usás solo fallback global).
- [ ] En **multi-merchant** producción: `WHATSAPP_ALLOW_GLOBAL_FALLBACK=false` y cada tienda con credenciales propias.
- [ ] Registro de nuevas tiendas: el comercio debe **activar** WhatsApp en configuración (`whatsapp_enabled` empieza en `false` tras registro).

## 4. Webhook (MS-I07)

- [ ] URL pública **HTTPS**: `{APP_BASE_URL}/webhooks/whatsapp` (sin slash final extra que rompa la ruta).
- [ ] En Meta → Webhooks: mismo path, **Verify token** = `WHATSAPP_WEBHOOK_VERIFY_TOKEN`.
- [ ] `META_APP_SECRET` en el servidor coincide con la app (firma `X-Hub-Signature-256`).
- [ ] Suscripción al producto **whatsapp_business_account** con campos que envíen `statuses` (trazabilidad de entrega).
- [ ] Probar **GET** (verificación) y un **POST** de prueba; revisar logs de la app.

## 5. Infra y worker

- [ ] `DATABASE_URL`, migraciones Alembic aplicadas (incl. columnas WhatsApp en `store_settings`).
- [ ] Worker de reconciliación ecommerce en ejecución; Tiendanube OAuth + `ecommerce_sync_enabled` coherentes con el piloto.
- [ ] **Observabilidad:** `GET /ready` para probes de DB; `GET /metrics` es **público** en el código actual (sin auth) — si exponés la app a internet, valorar firewall o deshabilitar la ruta hasta endurecer MS-I05.
- [ ] Revisar logs ante **429**: el motor respeta `Retry-After` entre reintentos; errores de plantilla/config no deberían reintentarse en vano (heurística en código).

## 6. Prueba end-to-end mínima

- [ ] Pedido de prueba con teléfono en allowlist de Meta (o producción): transición a `in_transit` / `delivered` dispara template y aparece registro en `NotificationAttempt`.
- [ ] Panel: estadísticas / errores coherentes si un envío falla.

## 7. Cumplimiento (recordatorio)

- [ ] Uso de número del cliente alineado a políticas de Tiendanube / opt-in y categoría UTILITY (detalle en `docs/SPEC.md` Parte I y tareas MS-I08 en `MILESTONES.md`).

---

**Referencia rápida de variables**: `.env.example` y tabla en `WHATSAPP_META.md` §1.
