# Arquitectura

## Componentes

```mermaid
flowchart TB
    U[Usuarios: asesor, supervisor y administrador] --> FE[Frontend React + Vite]
    FE -->|REST /api/v1 y JWT| API[FastAPI]
    API --> DB[(PostgreSQL)]
    API --> XLSX[OpenPyXL: importación y reportes]
    API --> SCH[Planificador de alertas]
    SCH --> DB
    MIG[Alembic] --> DB
```

| Capa | Tecnología | Responsabilidad |
| --- | --- | --- |
| Interfaz | React 19, TypeScript, Vite, Recharts | Operación, paneles, formularios y descargas. |
| API | FastAPI, Pydantic, SQLAlchemy | Autenticación, reglas de negocio y autorización por rol. |
| Persistencia | PostgreSQL 17 | Datos operativos, auditoría e historial de asignaciones. |
| Migraciones | Alembic | Evolución controlada del esquema. |
| Archivos | OpenPyXL | Plantillas, previsualización de Excel y reportes operativos. |
| Entorno | Docker Compose, Nginx | Ejecución local y despliegue. |

## Módulos Del Backend

```mermaid
flowchart LR
    AUTH[Auth y usuarios] --> CUST[Clientes y cartera]
    CUST --> SALE[Ventas e ítems]
    PROD[Productos y reglas] --> SALE
    SALE --> ALERT[Alertas]
    ALERT --> SUP[Supervisión y recuperación]
    SALE --> REPORT[Reportes]
    ALERT --> REPORT
    IMPORT[Importaciones] --> CUST
    IMPORT --> PROD
    IMPORT --> SALE
    AUDIT[Auditoría] --- CUST
    AUDIT --- SALE
    AUDIT --- ALERT
```

## Modelo De Datos

```mermaid
erDiagram
    USERS ||--o{ CUSTOMERS : "responsable de cartera"
    USERS ||--o{ SALES : "registra"
    CUSTOMERS ||--o{ SALES : realiza
    SALES ||--|{ SALE_ITEMS : contiene
    PRODUCTS ||--o{ SALE_ITEMS : vendido_en
    PRODUCTS ||--o{ PRODUCT_REPURCHASE_RULES : define
    SALE_ITEMS ||--o{ ALERTS : genera
    ALERTS ||--o{ ALERT_CONTACT_ATTEMPTS : registra
    ALERTS ||--o{ ALERT_ASSIGNMENT_HISTORY : reasigna
    CUSTOMERS ||--o{ CUSTOMER_ASSIGNMENT_HISTORY : transfiere
    SALES ||--o| SALES : reemplaza
    ALERTS ||--o| SALES : origina_recompra
```

### Invariantes Relevantes

- Un DNI identifica a un único cliente.
- Una venta histórica usa `numero_venta` como referencia externa única e idempotente.
- Cada ítem conserva precio unitario, regla y fecha esperada aplicados en el momento de la venta.
- Una alerta solo puede vincular una recompra del producto esperado.
- Alertas, contactos y reasignaciones quedan auditados.
- Ventas con historial de alertas o recompra no permiten cambios destructivos en fecha o productos; se anulan y reemplazan.

## Seguridad

La API usa JWT con expiración. Los asesores están restringidos a su cartera para clientes, ventas y alertas; supervisores y administradores acceden a operación y reportes. El frontend nunca almacena contraseñas, solo el token de sesión en almacenamiento local.
