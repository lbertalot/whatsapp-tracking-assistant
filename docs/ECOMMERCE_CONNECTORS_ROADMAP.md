# Roadmap — Conectores ecommerce

**Estado:** plan de producto; el MVP implementa solo **Tiendanube**.

## Principio

Cada conector debe proveer:

1. **Autenticación / instalación** (OAuth, app embed o claves de API según plataforma).
2. **Ingesta de órdenes** (webhooks + compensación por API).
3. **Modelo normalizado** hacia `Order` + `StoreInstallation.order_source_type`.
4. **Mapeo de estado** de envío → `in_transit` / `delivered` (y futuros estados si el producto los agrega).
5. **Pruebas** con mocks de API y contratos documentados.

## Prioridad sugerida (ajustable por negocio)

| Orden | Plataforma   | Complejidad típica | Notas |
|-------|--------------|-------------------|--------|
| 1     | Tiendanube   | —                 | **En producción (MVP)** |
| 2     | Shopify      | Alta              | OAuth, webhooks, GraphQL Admin API |
| 3     | WooCommerce  | Media–Alta        | REST + plugin o Application Password; multi-sitio |
| 4     | Magento      | Alta              | OAuth2, integraciones enterprise |
| 5     | PrestaShop   | Media             | Webservice API, módulo |

## Dependencias transversales

- **Multi-tenant:** un `Store` puede tener varias `StoreInstallation` con distinto `order_source_type` (futuro); hoy TN es el camino feliz.
- **Privacidad:** cada plataforma tiene políticas de datos del comprador; revisar términos y bases legales por país (LatAm).

## Entregables por conector (epic)

- Documento de mapeo de estados (tabla raw → interno).
- Variables de entorno / credenciales por app.
- Suite de tests de integración con HTTP mock.
- Actualización de onboarding en panel (“Conectar Shopify”, etc.).

---
