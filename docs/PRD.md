# PRD v2 — WhatsApp Post-Purchase Assistant (Paraguay)

---

## 1. Problema (Dolor real)

En Paraguay, los e-commerce que operan con soluciones como Weraha enfrentan un problema crítico post-compra:

### Para el comprador:

* Incertidumbre sobre el estado del pedido
* Dependencia total de WhatsApp para comunicación
* Falta de notificaciones proactivas

### Para el merchant:

* Alto volumen de consultas manuales (“¿dónde está mi pedido?”)
* Gestión manual por WhatsApp
* Falta de visibilidad sobre qué fue comunicado al cliente

---

## 2. ICP (Ideal Customer Profile)

### Segmento objetivo:

* País: Paraguay
* Volumen: 50–500 órdenes por mes
* Logística: usan Weraha
* Canal de soporte: WhatsApp manual
* Madurez:

  * no usan CRM complejo
  * no tienen automatización avanzada

---

## 3. Propuesta de valor (Diferenciación)

> “Automatizamos y te mostramos cada notificación de envío por WhatsApp para que dejes de responder ‘¿dónde está mi pedido?’”

---

## Diferenciadores clave:

### 1. Foco extremo (NO CRM, NO chatbot)

* solo post-compra
* solo tracking

---

### 2. Confiabilidad

* eventos simples
* sin complejidad

---

### 3. Visibilidad (VENTAJA PRINCIPAL)

* el merchant ve:

  * qué evento/template se envió
  * cuándo
  * si falló
  * por qué

---

### 4. Onboarding ultra simple

* <10 minutos
* sin integraciones complejas
* **Registro self-service** (`/register`): el vendedor crea email/contraseña y nombre de tienda; luego vincula Tiendanube (OAuth) desde el panel — sin depender de credenciales fijas en variables de entorno en despliegue normal (ver **MS-ONB02** / **MS-ONB01** en `docs/MILESTONES.md`).

Supuesto:

* credenciales de Weraha disponibles
* canal WhatsApp y templates ya configurados o listos para activar

---

## 4. Solución (MVP)

Sistema que:

* recibe órdenes
* consulta estado logístico (Weraha)
* envía notificaciones por WhatsApp
* muestra estado de cada notificación

---

## 5. Funcionalidades MVP

### ✔️ Incluye:

* integración con fuente de órdenes
* integración con Weraha
* normalización de teléfonos
* notificaciones WhatsApp
* panel mínimo de visibilidad

---

### ❌ No incluye:

* CRM
* chatbot
* múltiples couriers
* múltiples países
* analytics avanzados

---

## 6. Eventos soportados

* En tránsito
* Entregado

---

## 7. Experiencia del usuario

### Mensajes:

**En tránsito:**

> Tu pedido #123 ya está en camino 🚚

**Entregado:**

> Tu pedido #123 fue entregado ✅

---

## 8. Métricas clave

### Activación:

* tiempo a primera notificación < 1 día

### Uso:

* % órdenes notificadas

### Resultado:

* reducción de consultas WISMO
* feedback merchant

Nota:

* reducción de WISMO y feedback merchant se validan inicialmente de forma manual en pilotos

---

## 9. Go-To-Market

### Estrategia dual:

#### 1. Directo (pilot)

* 3–5 tiendas Paraguay
* onboarding manual

---

#### 2. Canal especialistas

* agencias locales
* implementadores
* partners

---

## 10. Hipótesis clave

* merchants en Paraguay priorizan simplicidad sobre features
* WhatsApp es canal dominante
* visibilidad genera confianza
* reducción de WISMO es valor pagable

---

## 11. Riesgos

* calidad de teléfonos
* tracking incompleto
* dependencia WhatsApp
* baja adopción si onboarding es complejo

---

## 12. Definición de éxito

### Éxito técnico:

✔️ notificaciones funcionando
✔️ visibilidad utilizada

### Éxito de producto:

✔️ 3 tiendas activas
✔️ merchant percibe reducción de soporte

---

## 13. Principios

* simplicidad > features
* visibilidad > automatización
* velocidad > perfección

---