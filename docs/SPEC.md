# WhatsApp Tracking Assistant — Especificación unificada

Este documento consolida **producto (PRD)**, **diseño técnico (RFC)** y **decisiones de arquitectura (ADRs)**. Es la fuente de verdad única para alcance y comportamiento; el roadmap de conectores ecommerce está en [`ECOMMERCE_CONNECTORS_ROADMAP.md`](ECOMMERCE_CONNECTORS_ROADMAP.md).


---

## Parte I — Producto (PRD v3)

### 1. Problema (dolor real)

En **Latinoamérica**, los e‑commerce que venden por canal propio enfrentan un problema crítico post‑compra:

#### Para el comprador

- Incertidumbre sobre el estado del pedido
- Dependencia de WhatsApp para comunicación
- Falta de notificaciones proactivas desde la **tienda** donde compró

#### Para el merchant

- Alto volumen de consultas manuales (“¿dónde está mi pedido?”)
- Gestión manual por WhatsApp
- Falta de visibilidad sobre qué se comunicó al cliente

La **fuente de verdad operativa** del envío debe ser la **plataforma de ecommerce** (pedido, fulfillment, tracking que ya gestiona la tienda), no un operador logístico externo por integración, para evitar N integraciones courier y duplicar datos que el ecommerce ya concentra.

---

### 2. ICP (Ideal Customer Profile)

#### Segmento objetivo

- **Región**: Latinoamérica (priorización por país según GTM; ej. PY, AR, MX, CO, BR, CL…)
- **Volumen**: 50–500 órdenes por mes (tunable)
- **Stack**: tienda online (MVP: **Tiendanube**; roadmap: Shopify, WooCommerce, Magento, PrestaShop)
- **Canal de soporte**: WhatsApp manual
- **Madurez**: sin CRM complejo; poca automatización avanzada

---

### 3. Propuesta de valor

> “Automatizamos y te mostramos cada notificación de envío por WhatsApp a partir de los datos de **tu tienda**, para que dejes de responder ‘¿dónde está mi pedido?’”

---

### 4. Diferenciadores clave

1. **Foco extremo** (no CRM, no chatbot): solo post‑compra y tracking.
2. **Confiabilidad**: eventos simples, flujo auditable.
3. **Visibilidad**: el merchant ve qué template se envió, cuándo, si falló y por qué.
4. **Onboarding simple**: registro self‑service, OAuth Tiendanube desde el panel.
5. **Un conector ecommerce en el MVP (Tiendanube)**; el mismo producto puede sumar plataformas sin reescribir el núcleo de notificaciones.

---

### 5. Solución (MVP)

Sistema que:

- Recibe órdenes desde la **tienda conectada** (webhooks + API)
- **Deriva el estado logístico** desde datos de ecommerce (no desde un courier único obligatorio)
- Envía notificaciones por WhatsApp (Meta Cloud API)
- Muestra trazabilidad en panel

---

### 6. Funcionalidades MVP

#### Incluye

- Integración con fuente de órdenes (**Tiendanube** en v1)
- Normalización de teléfonos (E.164; región por tienda cuando falta prefijo)
- Notificaciones WhatsApp con idempotencia
- Panel mínimo de visibilidad
- Sincronización periódica con la API de la tienda como respaldo de webhooks

#### No incluye (explícito)

- CRM, chatbot, analytics avanzados
- **Integración obligatoria con un operador logístico concreto** como fuente de verdad
- Cobertura simultánea de **todas** las plataformas en el primer release (solo TN)

---

### 7. Eventos soportados (mensajes)

- En tránsito
- Entregado

---

### 8. Experiencia de usuario (mensajes)

**En tránsito:** Tu pedido #123 ya está en camino 🚚  

**Entregado:** Tu pedido #123 fue entregado ✅  

---

### 9. Métricas clave

- Activación: tiempo a primera notificación &lt; 1 día
- Uso: % órdenes notificadas
- Resultado: reducción consultas WISMO; feedback merchant (piloto)

---

### 10. Go-To-Market

- Pilotos directos en **2–3 países** cuando aplique
- Partners: agencias e implementadores regionales

---

### 11. Legal / datos (orientativo)

Cumplimiento de privacidad y tratamiento de datos personales depende del país (p. ej. LGPD en Brasil, normas locales). **Validar con asesor legal** antes de escalar.

---

### 12. Riesgos

- Calidad de teléfonos capturados en checkout
- Cobertura de eventos según cómo cada merchant usa TN (webhooks + API)
- Dependencia del canal WhatsApp / Meta
- Complejidad futura al sumar conectores (mitigar con interfaz común)

---

### 13. Definición de éxito

**Técnico:** notificaciones funcionando; visibilidad usada; estados coherentes con la tienda.

**Producto:** tiendas activas; percepción de reducción de soporte.

---

### 14. Principios

- Simplicidad &gt; features  
- Visibilidad &gt; automatización  
- Velocidad &gt; perfección  

---

## Parte II — Diseño técnico (RFC v3)

### 1. Objetivo

Sistema que:

- ingiere órdenes desde la **plataforma de ecommerce** (MVP: **Tiendanube**)
- **deriva el estado logístico** desde datos de la tienda (webhooks + API + worker de reconciliación)
- envía notificaciones WhatsApp (Meta Cloud API)
- expone visibilidad completa al merchant (panel)

### 2. Arquitectura

```
[Ecommerce Platform: TN API / Webhooks]
        ↓
[FastAPI API]
        ↓
[PostgreSQL]
        ↓
[Sync Worker — GET periódico orden TN]
        ↓
[tiendanube_order_status + Notification Engine]
        ↓
[WhatsApp Service]
```

### 3. Componentes

#### 3.1 Ingesta de órdenes

- Webhooks Tiendanube (`order/created`, `order/paid`, `order/fulfilled`) con validación HMAC
- Fetch de detalle de orden cuando el payload mínimo no alcanza (ver **ADR-003** en la Parte III)

#### 3.2 Normalización de teléfonos

- `phonenumbers` → E.164
- Región por defecto: `StoreSettings.default_phone_region` o `Store.country` (ISO-2)

#### 3.3 Worker (reconciliación)

- Bucle con intervalo configurable (`POLL_INTERVAL_SECONDS`)
- Para órdenes no terminales: `GET` orden TN con `aggregates=fulfillment_orders` y actualización de estado
- Respeta `StoreSettings.ecommerce_sync_enabled`

#### 3.4 Mapeo de estado ecommerce → interno

- `map_tiendanube_order_detail()` → `in_transit` | `delivered` | `None`
- Campos de auditoría: `orders.platform_status_raw`, `orders.last_status_source`

#### 3.5 Motor de notificaciones

- Idempotencia `store_id:order_id:event_type`
- Plantillas Meta por evento

#### 3.6 WhatsApp Service

- Meta Cloud API (Graph)

### 4. Fuera de alcance técnico (MVP)

- CRM, chatbot, analytics avanzados
- **Operador logístico** como fuente de verdad obligatoria
- Segundo conector ecommerce en el mismo release (ver roadmap)

### 5. Modelo de tenancy

Tablas mínimas: `stores`, `store_installations`, `store_settings`, `store_users`  
Objetivo: multi-merchant desde el MVP; aislamiento por `store_id`.

`store_settings` incluye (entre otros):

- `ecommerce_sync_enabled` — activar/desactivar sync periódico desde la API TN
- `default_phone_region` — ISO-2 para parseo de teléfonos
- configuración WhatsApp y onboarding

### 6. Modelo de datos (órdenes)

Campos clave en `orders`:

- `current_status` — interno: `pending_tracking`, `in_transit`, `delivered`, etc.
- `platform_status_raw` — último estado crudo reportado por la tienda
- `last_status_source` — `webhook` | `sync`

### 7. Historial e idempotencia

Tabla `notification_attempts` con `idempotency_key` único.

### 8. Autenticación

JWT por tienda; todas las queries de panel filtradas por `store_id`.

### 9. Observabilidad

- `GET /health`, `GET /ready`
- Logs estructurados en eventos clave (ingesta, cambio de estado, envío WA, error API TN)

### 10. Seguridad

- Variables de entorno para secretos
- Webhook TN: HMAC
- Webhook Meta: verify token + firma `X-Hub-Signature-256`

---

## Parte III — Decisiones de arquitectura (ADRs)

### ADR-001 — Stack Tecnológico y Arquitectura Base

#### Contexto

Se requiere construir un MVP para un sistema de notificaciones post-compra vía WhatsApp con foco en:

* simplicidad
* velocidad de desarrollo
* bajo costo
* capacidad de iteración rápida
* visibilidad vendible al merchant desde el día 1

Basado en la **Parte I** (producto) y la **Parte II** (RFC) de este documento, el MVP incluye:

* ingestión de órdenes
* estado de envío derivado de la **plataforma ecommerce** (Tiendanube en v1)
* envío de notificaciones por WhatsApp
* panel de visibilidad para merchant

El producto NO busca resolver:

* CRM
* chatbot
* múltiples plataformas ecommerce en el mismo release (MVP: una; roadmap en `docs/ECOMMERCE_CONNECTORS_ROADMAP.md`)
* analytics avanzados

---

### Decisión

Se adopta una arquitectura monolítica, priorizando velocidad y bajo costo operativo.

#### Backend

* **FastAPI (Python)**

#### Base de datos

* **PostgreSQL**

#### Infraestructura

* **Heroku**

#### Frontend

* **UI vendible desde el día 1**
* **No se adopta Next.js en el MVP**
* el panel se implementa como una UI integrada más simple dentro del backend
* la prioridad es reducir tiempo total a valor y costo operativo

#### Repositorio

* **GitHub**

#### Entorno de desarrollo

* **Cursor IDE**

---

### Justificación

#### FastAPI

✔️ Alta velocidad de desarrollo  
✔️ Async-ready para polling e IO externo  
✔️ Encaja naturalmente con servicios, workers y adapters descritos en la Parte II

---

#### PostgreSQL

✔️ Relacional, adecuado para órdenes, estados y trazabilidad  
✔️ Permite consultas simples para panel de visibilidad  
✔️ Compatible con despliegue rápido en Heroku

---

#### Heroku

✔️ Deploy rápido  
✔️ Bajo overhead DevOps  
✔️ Permite separar procesos web y worker  
✔️ Tiene un camino simple para scheduler y base de datos en MVP

❌ No optimizado para costo a escala  
❌ No es la opción final si el producto valida y aumenta volumen

---

#### UI vendible desde día 1

✔️ El panel no es soporte interno: es parte del producto  
✔️ Debe mostrar valor visible al merchant desde la primera demo  
✔️ Debe poder enseñar:

* lista de órdenes
* estado actual
* última notificación enviada
* error visible
* timestamp

---

#### UI integrada como decisión final de MVP

✔️ Reduce despliegues, coordinación y costo operativo  
✔️ Mantiene el principio de monolito primero  
✔️ Es suficiente para un panel vendible en pilotos pagos

❌ Puede limitar flexibilidad visual futura  
❌ Si el producto valida y necesita una UX más sofisticada, podrá extraerse luego a un frontend separado

---

#### GitHub

✔️ Control de versiones  
✔️ Base razonable para CI/CD futura

---

#### Cursor

✔️ Acelera scaffolding  
✔️ Reduce tiempo de traducción entre la especificación (Partes I–III) y la ejecución

---

### Tradeoffs

| Decisión | Beneficio | Costo |
| --- | --- | --- |
| Monolito | rapidez y menor complejidad | menor escalabilidad inicial |
| Heroku | simplicidad operativa | costo futuro y menor flexibilidad |
| Sync periódico + webhooks | resiliencia si falta un evento | más llamadas API que un solo webhook perfecto |
| Meta API directo | menos intermediarios | integración inicial más sensible |
| UI vendible desde día 1 | mejor percepción de valor | requiere priorizar frontend antes |
| UI integrada en backend | menor costo y menor fricción | menor flexibilidad visual futura |

---

### Arquitectura General

```mermaid
flowchart TD
    A[Ecommerce API / Webhooks] --> B[FastAPI API]
    B --> C[PostgreSQL]
    C --> D[Sync Worker]
    D --> E[Tiendanube order status]
    E --> F[Notification Engine]
    F --> G[WhatsApp Meta API]
    B --> H[Integrated Merchant UI]
    H --> C
```

---

### Flujo de notificación

```mermaid
sequenceDiagram
    participant TN as Tiendanube
    participant API as FastAPI
    participant DB as PostgreSQL
    participant W as Worker
    participant WA as WhatsApp API
    participant UI as Merchant UI

    TN->>API: Webhook order / fulfilled
    API->>DB: Save or update order
    UI->>API: Consult visible orders
    API->>DB: Read order state
    API-->>UI: Order list and visibility

    loop Reconciliation
        W->>TN: GET order (sync)
        TN-->>W: Order JSON
        W->>DB: Update status from ecommerce
        W->>WA: Send template if pending
        WA-->>W: Response
        W->>DB: Log notification attempt
    end
```

---

### Infraestructura operativa mínima

Se define una operación mínima consistente con la Parte II:

* **web process** para API y panel
* **worker process** para polling, mapeo y notificaciones
* **scheduler** para disparar ejecución periódica del polling
* **PostgreSQL** como fuente única de verdad

Objetivo operativo del MVP:

* mantener webhook, worker y panel con confiabilidad suficiente para pilotos pagos
* sostener tiempo a primera notificación menor a 1 día en tiendas correctamente configuradas

---

### Multi-merchant y aislamiento

Se decide que el MVP será multi-merchant desde la primera versión vendible.

Reglas:

* toda entidad de negocio se asocia a `store_id`
* el panel no es interno: cada merchant accede solo a su información
* órdenes, errores, configuraciones y visibilidad quedan aisladas por tienda

---

### Acceso al panel

Se adopta autenticación propia simple para el MVP.

Decisiones:

* cada merchant tendrá usuario y contraseña
* cada usuario pertenece a una sola tienda
* el panel filtra toda consulta por `store_id`
* no se implementan roles complejos ni SSO en esta fase

---

### Trazabilidad e idempotencia

Se adopta persistencia explícita de intentos de notificación.

Decisiones:

* cada intento se registra en una tabla dedicada
* la clave de idempotencia será `store_id:order_id:event_type`
* el sistema no debe enviar dos veces una notificación final exitosa para el mismo evento
* el panel mostrará el último estado visible a partir de esta trazabilidad

---

### Configuración por tienda

Se decide persistir configuración operativa por tienda en base de datos.

Incluye:

* configuración de sincronización ecommerce y WhatsApp
* estado de activación
* configuración de WhatsApp
* templates habilitados
* resultado de pruebas de onboarding

Esto evita depender de configuración global por aplicación para tiendas distintas.

---

### Topología de despliegue

La topología mínima del MVP en Heroku será:

* **web dyno** para API y panel
* **worker dyno** para polling, mapeo y notificaciones
* **scheduler** para disparar polling
* **postgres** como base única

---

### Estructura de repositorio

```bash
backend/
  app/
    api/
    services/
    models/
    workers/
    db/
    templates/
    static/

docs/
  SPEC.md
```

Regla:

* la UI del MVP vive integrada al backend
* no se introduce un frontend separado en esta fase

---

### Estrategia de desarrollo

#### Fase 1

* backend funcional
* base de datos
* ingestión de órdenes
* modelo multi-merchant base
* estructura de visibilidad en modelo de datos
* autenticación simple
* endpoint inicial para panel
* UI mínima vendible del merchant

---

#### Fase 2

* worker de reconciliación con API Tiendanube
* mapeo de estado desde payload de tienda → estados internos
* actualización de estados visibles

---

#### Fase 3

* integración WhatsApp API
* envío real de notificaciones
* registro de errores, retries y trazabilidad visible
* persistencia de onboarding y configuración por tienda

---

#### Fase 4

* endurecimiento operativo
* mejoras UX/UI
* métricas de piloto
* refinamiento de onboarding

---

### Lineamientos de UI del panel

Como el panel es parte vendible del MVP, debe cubrir desde la primera versión:

* acceso autenticado
* lista de órdenes
* estado logístico actual
* estado de notificación
* último evento/template enviado
* fecha de última notificación
* error visible si existe

Elementos opcionales, pero NO requeridos para MVP:

* filtros avanzados
* analytics avanzados
* roles complejos
* branding multi-tenant avanzado

---

### Herramientas de diseño recomendadas

#### Recomendación principal

* **Penpot**

Sirve para:

* wireframes rápidos
* mockups de validación
* iteración con foco en claridad del panel

#### Alternativas

* **Excalidraw** para flujos rápidos
* **tldraw** para diagramas simples

---

### Principios de arquitectura

* monolito primero
* desacoplar después
* observable desde el día 1
* panel vendible desde el día 1
* multi-merchant desde el día 1
* evitar sobreingeniería
* elegir la opción que reduzca tiempo total a valor

---

### ADR-002 — Onboarding Tiendanube (OAuth `state` + mismo `Store`)

#### Contexto

El callback OAuth de Tiendanube (MS-I01) puede crear o actualizar un `Store` solo por `user_id` de TN, desalineado del merchant que ya inició sesión en el panel con otro `store_id` (JWT). Se necesita vincular la instalación TN al **mismo** `Store` del usuario autenticado.

#### Decisión

1. **`state` OAuth = JWT de corta vida** firmado con `SECRET_KEY`, con `store_id`, `purpose: tn_oauth` y expiración (15 min). Se genera en `GET /api/integrations/tiendanube/install-url` (requiere Bearer) y TN lo devuelve en el callback.
2. **Callback con `state`**: intercambio de código, actualización de `Store`, `StoreInstallation` y redirección **HTTP 302** a `{APP_BASE_URL}/onboarding?success=1` o `?error=…` para UX en navegador (no 409 JSON en este flujo).
3. **Conflictos**: si el `Store` ya tiene `external_store_id` distinto al `user_id` TN → redirect `error=store_conflict` (desvincular / soporte fuera de MVP).
4. **Legacy sin `state`**: se conserva respuesta JSON para instalaciones iniciadas desde el ecosistema TN sin panel.
5. **Token endpoint**: `exchange_code` envía cuerpo **JSON**; si en producción TN exigiera solo `form-urlencoded`, añadir fallback documentado.

#### Consecuencias

* Gating en panel (`needs_tiendanube`) y guards en plantillas alinean órdenes/webhooks futuros al `store_id` correcto.
* El merchant siempre pasa por flujo autenticado antes de autorizar TN en el escenario “panel primero”.
* UX: guía pública `/ayuda/conectar-tiendanube`, onboarding con pasos y URLs copiables expuestas vía `GET /api/onboarding/status` para reducir fricción y tickets de soporte.
* **Seed local:** `SEED_TN_LINK_MODE=oauth_ready` evita `external_store_id` ficticio (`demo-paraguay-tn`) que provocaba `store_conflict` al vincular una tienda TN real; modo `demo` conserva el panel “precargado” sin OAuth.

---

### ADR-003 — Webhooks de pedido Tiendanube (payload mínimo + fetch API)

#### Contexto

Los webhooks de TN para `order/*` solo incluyen `store_id`, `event` e `id` de la orden ([documentación oficial](https://tiendanube.github.io/api-documentation/resources/webhook)). No alcanza para teléfono ni tracking.

#### Decisión

1. Tras validar HMAC, resolver `Store` por `external_store_id == str(store_id)` y obtener `access_token` de `StoreInstallation` TN activa.
2. **`order/created` / `order/paid`**: `GET /v1/{user_id}/orders/{id}` → persistir `Order` con `contact_phone` / `customer` según respuesta API.
3. **`order/fulfilled`**: priorizar tracking en el cuerpo del POST si viene (`shipping_*` o `tracking_info`); si no, `GET` con `aggregates=fulfillment_orders` y leer `tracking_info.code` en `fulfillment_orders` / `fulfillments`.
4. **Rendimiento**: timeout ~2,5s en el cliente HTTP; si orden existe y el webhook trae tracking, no llamar a la API.
5. **Errores transitorios de API**: responder **503** para que TN reintente; sin token TN → **200** `ignored` (evita reintentos infinitos por config rota).
6. **`store/redact`**: `Store.status = redacted`, instalaciones TN `is_active=False` (worker ya filtra `status=active`).

#### Consecuencias

* Dependencia de token válido y scopes (p. ej. lectura de órdenes) en la app TN.
* Menos “magia” sobre payloads no documentados; tests usan mock de API.

---

### ADR-004 — Registro merchant self-service (`POST /auth/register`)

#### Contexto

Depender de `SEED_USER_EMAIL` / `SEED_USER_PASSWORD` en `.env` para “el usuario del panel” no escala a producción ni refleja el flujo real del vendedor; además genera confusión en Docker/logs cuando esas variables faltan o no coinciden con el seed.

#### Decisión

1. **`POST /auth/register`**: body JSON con `email`, `password` (mín. 8 caracteres) y `store_name` o `storeName` (2–150 caracteres); crea en una transacción `Store` (sin `external_store_id` hasta OAuth), `StoreSettings` con `onboarding_status=pending`, `StoreUser` con `role=owner`; responde **201** + `LoginResponse` (JWT).
2. **Email duplicado**: **409** con mensaje claro; `IntegrityError` en commit también se mapea a 409.
3. **UI**: `GET /register` (Jinja); enlaces desde login y ayuda pública; tras registro, redirigir a `/onboarding` si `needs_tiendanube`.
4. **`GET /me`**: expone `tiendanube_user_id` (`Store.external_store_id`) y `needs_tiendanube` (misma regla que `GET /api/onboarding/status`: instalación TN activa con token).
5. **Seed demo**: credenciales por defecto definidas en `scripts/seed_demo_data.py`; `SEED_USER_*` solo si hace falta otro email/contraseña para dev/CI.

#### Consecuencias

* Milestone **MS-ONB02** en `docs/MILESTONES.md`; alineado con **MS-ONB01** (OAuth después de tener cuenta).
* Despliegue normal sin usuario “mágico” en variables de entorno; el demo técnico sigue disponible vía script.

---

### ADR-005 — WhatsApp Cloud API (Meta): plantillas, errores Graph y webhook

#### Contexto

El envío mínimo a `/{phone-number-id}/messages` sin `template.components` falla cuando las plantillas tienen variables. Meta exige webhook con verificación y firma `X-Hub-Signature-256` para producción y buenas prácticas. Los milestones **MS-I06** e **MS-I07** en `docs/MILESTONES.md` detallan el alcance.

#### Decisión

1. **Plantillas con parámetros**: si `send_template_message` recibe `params`, se arma `template.components` con un bloque `body` y parámetros `type: text` en orden estable: `order_id` primero, luego el resto de claves alfabéticamente. Flag `whatsapp_include_body_params` para plantillas sin variables.
2. **Errores HTTP**: parsear JSON `error.code` / `message`; propagar `Retry-After`; heurística `graph_send_error_may_benefit_from_retry` para no reintentar errores permanentes.
3. **Webhook** (`GET` + `POST /webhooks/whatsapp`): verify token + firma `META_APP_SECRET` en POST.
4. **Trazabilidad de entrega**: `NotificationAttempt` con `provider_delivery_status` correlacionado por `wamid`.
5. **Credenciales por tienda (MS-I08)**: `store_settings` + `resolve_for_store`; fallback opcional `WHATSAPP_ALLOW_GLOBAL_FALLBACK`; `whatsapp_enabled` en el motor de notificaciones.

#### Consecuencias

* Migraciones Alembic en `notification_attempts` y `store_settings`.
* Ver `docs/WHATSAPP_META.md` y `docs/META_GO_LIVE_CHECKLIST.md`.

---

### ADR-006 — Fuente de verdad: ecommerce (no operador logístico obligatorio)

#### Contexto

Acoplar el MVP a un único proveedor de tracking externo (courier) implica N integraciones a medida y duplica datos que la tienda ya gestiona. El producto prioriza **Latinoamérica** y **varias plataformas de tienda en el tiempo**, empezando por Tiendanube.

#### Decisión

1. El **estado de envío** que dispara las plantillas WhatsApp se obtiene de **datos de la tienda** (webhooks + API de Tiendanube en v1), con campo de auditoría `orders.platform_status_raw` y `last_status_source` (`webhook` | `sync`).
2. Se **elimina** el adaptador de courier **Weraha** del núcleo del MVP y los campos `weraha_*` en `store_settings`; el worker pasa a ser **reconciliación** contra la API de TN.
3. `StoreSettings.ecommerce_sync_enabled` permite pausar la sincronización automática; `default_phone_region` ayuda a normalizar teléfonos sin prefijo internacional en LatAm.
4. Nuevas plataformas (Shopify, WooCommerce, Magento, PrestaShop) se documentan como **roadmap** (`docs/ECOMMERCE_CONNECTORS_ROADMAP.md`) y deberían implementarse como conectores con la misma interfaz mental: ingestión + mapeo de estado + notificaciones.

#### Consecuencias

* Menos dependencia operativa de un contrato courier único.
* Mayor responsabilidad en **mapeo robusto** de estados TN (evoluciona con la API).
* ADR-003 sigue siendo la base de webhooks; el worker complementa con GET periódico.

---

### Resultado esperado

Con este ADR:

✔️ el equipo tiene una arquitectura consistente con la Parte I y la Parte II de este documento  
✔️ el panel se trata como parte central del producto  
✔️ se reduce el riesgo de sobreingeniería en frontend  
✔️ se acelera el time-to-first-user con una base operativamente simple

---
