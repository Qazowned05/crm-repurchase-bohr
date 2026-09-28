# Fase 0 - Definicion funcional de arranque

## Estado

Esta fase deja listo el alcance funcional para iniciar la Fase 1. Todos los datos de ejemplo son ficticios.

## Decisiones operativas iniciales

Los siguientes valores se cargaran como configuracion administrable. Son valores iniciales de desarrollo, no constantes del codigo.

| Parametro | Valor inicial | Regla |
|---|---:|---|
| Ventana activa posterior a recompra | 30 dias | Una alerta sin gestion ni reprogramacion pasa a vencida al terminar esta ventana. |
| Intentos maximos sin respuesta | 3 | Al superar el limite, la alerta pasa a cola de recuperacion. |
| Separacion minima entre intentos | 3 dias | La proxima accion no puede programarse antes de este intervalo. |
| Atraso maximo de proxima accion | 7 dias | Una alerta reprogramada vencida por este plazo se escala a recuperacion. |
| Ejecucion del proceso diario | 08:00 | Se ejecuta una vez al dia con la zona horaria configurada para la empresa. |
| Canales de captacion | TV, DIGITAL, OTROS | OTROS exige descripcion. Solo se captura en la primera venta confirmada del cliente. |

## Roles

| Rol | Responsabilidad principal |
|---|---|
| ASESOR | Registra sus ventas, consulta su cartera y gestiona sus alertas. |
| SUPERVISOR | Configura productos, revisa ventas excepcionales, reasigna cartera y monitorea indicadores. |
| ADMIN | Gestiona usuarios, permisos, configuracion global y todas las operaciones administrativas. |

## Historias de usuario prioritarias

### HU-01 - Iniciar sesion

Como usuario, quiero iniciar sesion para acceder solo a las funciones permitidas por mi rol.

**Aceptacion**

- Credenciales invalidas no crean sesion.
- Un usuario inactivo no puede iniciar sesion.
- Las rutas y acciones se protegen tambien en el backend.

### HU-02 - Buscar o crear cliente

Como asesor, quiero buscar un cliente por DNI antes de vender para no duplicar registros.

**Aceptacion**

- El DNI es obligatorio y unico.
- Si el cliente existe, se muestra su ficha e historial.
- Si no existe, puede crearse desde el flujo de venta.

### HU-03 - Configurar producto

Como supervisor, quiero configurar productos y reglas de recompra para calcular alertas por producto.

**Aceptacion**

- El producto tiene codigo unico, nombre, categoria y estado.
- La regla tiene duracion, dias previos de alerta, vigencia y aprobacion medica.
- Los dias de alerta son positivos, distintos y menores que la duracion.
- Un producto inactivo no puede agregarse a una venta nueva.

### HU-04 - Registrar primera venta

Como asesor, quiero registrar una venta con uno o varios productos para iniciar el seguimiento comercial.

**Aceptacion**

- La venta guarda cliente, asesor, fecha, productos, cantidades y observacion opcional.
- En la primera venta confirmada del cliente se exige canal de captacion.
- Se guarda una copia de la regla vigente en cada producto vendido.
- La primera venta de cada producto para ese cliente se clasifica como `COMPRA`.

### HU-05 - Registrar recompra

Como asesor, quiero registrar una recompra para actualizar el historial y cerrar el seguimiento previo.

**Aceptacion**

- Una venta posterior del mismo producto se clasifica como `RECOMPRA`.
- La venta referencia el producto vendido anterior.
- Si nace desde una alerta, esa alerta se marca `RECOMPRA_LOGRADA`.
- Las demas alertas activas del mismo cliente-producto quedan `CANCELADO_POR_RECOMPRA`.

### HU-06 - Prevenir ventas incorrectas

Como supervisor, quiero revisar ventas duplicadas o anuladas para proteger la calidad de las metricas.

**Aceptacion**

- Una posible venta duplicada queda `PENDIENTE_REVISION_DUPLICADO`.
- Solo supervisor o administrador aprueba una excepcion y registra el motivo.
- Una venta anulada conserva historial, no participa en metricas y no genera alertas.
- La anulacion recalcula el ciclo de compra/recompra afectado.

### HU-07 - Gestionar alertas

Como asesor, quiero una bandeja priorizada para atender oportunidades de recompra.

**Aceptacion**

- La alerta pertenece a un producto vendido especifico, no solo al cliente.
- La bandeja muestra vencidas recientes, hoy, proximas y reprogramadas.
- Las alertas son internas; el sistema no contacta automaticamente al cliente.
- La cantidad vendida no modifica la duracion ni las fechas de alerta.

### HU-08 - Tipificar un contacto

Como asesor, quiero registrar el resultado de una gestion para definir el siguiente paso.

**Aceptacion**

- Se registra fecha, canal usado, resultado, nota y proxima accion.
- Los resultados iniciales son: recompra registrada, aun tiene producto, solicita seguimiento, sin respuesta, no interesado, datos de contacto incorrectos y otro.
- Aun tiene producto y solicita seguimiento exigen proxima accion.
- Otro exige nota descriptiva.
- Una misma gestion puede registrar resultados independientes para varias alertas del cliente.

### HU-09 - Reasignar cartera

Como supervisor, quiero transferir cartera y alertas cuando un asesor deja de trabajar para que no se pierdan seguimientos.

**Aceptacion**

- El asesor saliente se desactiva, pero se conserva su historial.
- Clientes y alertas activas se reasignan a un asesor activo o a la cola de recuperacion.
- Cada transferencia conserva origen, destino, motivo, fecha y usuario responsable.

### HU-10 - Importar datos

Como supervisor, quiero importar clientes y productos desde plantillas Excel para iniciar la operacion rapidamente.

**Aceptacion**

- Solo se aceptan archivos `.xlsx` sin macros.
- Se valida el archivo antes de importar y se muestra una vista previa.
- Si una fila tiene error, el lote completo no se aplica.
- Se puede descargar el detalle de errores por fila.

### HU-11 - Consultar supervision

Como supervisor, quiero consultar indicadores para gestionar la cartera y el rendimiento.

**Aceptacion**

- Se muestran alertas, contactos, recompras, ventas y promedio entre compras.
- Los reportes separan asesor vendedor, responsable actual de cartera y asesor que gestiono la alerta.
- Se puede filtrar por periodo, asesor, producto y canal de captacion.

## Flujos principales

### Venta y alerta

1. El asesor busca al cliente por DNI.
2. Crea el cliente si no existe.
3. Registra la venta, productos y fecha.
4. Si es la primera venta del cliente, registra canal de captacion.
5. El sistema valida duplicados y confirma la venta o la envia a revision.
6. Al confirmar, guarda reglas aplicadas y clasifica cada producto como compra o recompra.
7. El proceso diario crea alertas por producto y fecha configurada.
8. El asesor tipifica la gestion o registra la recompra.

### Rotacion de asesor

1. Supervisor desactiva al asesor saliente.
2. Selecciona cartera y alertas activas.
3. Selecciona asesor destino o cola de recuperacion.
4. El sistema registra historial de transferencia.
5. Las nuevas alertas se asignan al responsable actual del cliente.

## Wireframes textuales

### Login

```text
+------------------------------------------------+
| CRM Fidelizacion                               |
|                                                |
| Correo       [____________________________]   |
| Contrasena   [____________________________]   |
|                                                |
|                 [ Ingresar ]                   |
|          Recuperar contrasena                  |
+------------------------------------------------+
```

### Bandeja del asesor

```text
+---------------------------------------------------------------+
| Alertas | Hoy: 4 | Vencidas: 2 | Proximas: 7 | [Filtros]     |
+---------------------------------------------------------------+
| VENCIDA  Cliente: Ana Torres                                  |
| Producto: Colageno | Recompra estimada: 20/10                 |
| [Gestionar] [Registrar recompra] [Reprogramar]                |
+---------------------------------------------------------------+
| HOY      Cliente: Luis Rios                                   |
| Producto: Omega 3 | Recompra estimada: 25/10                  |
| [Gestionar] [Registrar recompra] [Reprogramar]                |
+---------------------------------------------------------------+
```

### Venta

```text
+---------------------------------------------------------------+
| Nueva venta                                                    |
| DNI [____________] [Buscar]                                   |
| Cliente: Ana Torres                                            |
| Fecha [__/__/____]   Canal captacion [TV v]                   |
|                                                               |
| Producto             Cantidad        [Agregar producto]       |
| [Colageno       v]   [  1 ]                                   |
| [Omega 3        v]   [  1 ]                                   |
| Observacion [____________________________________________]    |
|                                      [Guardar venta]          |
+---------------------------------------------------------------+
```

### Gestion de alerta

```text
+---------------------------------------------------------------+
| Cliente: Ana Torres | Producto: Colageno                      |
| Canal usado [LLAMADA v]                                       |
| Resultado   [AUN_TIENE_PRODUCTO v]                            |
| Proxima accion [__/__/____]                                   |
| Nota [____________________________________________________]    |
|                                      [Guardar gestion]        |
+---------------------------------------------------------------+
```

### Importacion

```text
+---------------------------------------------------------------+
| Importar clientes o productos                                 |
| Tipo [Clientes v] [Descargar plantilla]                       |
| Archivo [____________________________] [Seleccionar]          |
|                                       [Validar archivo]       |
| Validas: 120 | Nuevas: 100 | Actualizables: 20 | Errores: 3   |
| [Descargar errores]                         [Importar lote]   |
+---------------------------------------------------------------+
```

## Modelo conceptual aprobado

```text
users 1---N sales 1---N sale_items N---1 products
customers 1---N sales
customers 1---N alerts (a traves de sale_items)
sale_items 1---N alerts 1---N contact_attempts
customers 1---N customer_assignments
alerts 1---N alert_assignments
products 1---N product_repurchase_rules
```

Entidades obligatorias: `users`, `customers`, `products`, `product_repurchase_rules`, `sales`, `sale_items`, `sales_duplicate_reviews`, `alerts`, `contact_attempts`, `alert_assignments`, `customer_assignments`, `import_jobs`, `import_row_errors`, `system_settings` y `audit_log`.

Restricciones principales:

- DNI y codigo de producto unicos.
- Una alerta es unica por `sale_item` y fecha programada.
- La confirmacion de recompra, su alerta de origen y la cancelacion de alertas restantes ocurren en una transaccion.
- Las ventas anuladas no pueden volver a confirmarse.

## Datos ficticios de prueba

### Usuarios

| Usuario | Rol | Estado |
|---|---|---|
| asesor.maria | ASESOR | Activo |
| asesor.jorge | ASESOR | Activo |
| supervisor.laura | SUPERVISOR | Activo |
| admin.sistema | ADMIN | Activo |

### Productos y reglas

| Codigo | Producto | Duracion | Alertas |
|---|---|---:|---|
| COL-001 | Colageno | 30 dias | 15 y 5 dias antes |
| OMG-001 | Omega 3 | 60 dias | 15 y 5 dias antes |
| VIT-001 | Vitamina D | 45 dias | 15 y 5 dias antes |

### Clientes y casos

| DNI ficticio | Cliente | Caso de prueba |
|---|---|---|
| 70000001 | Ana Torres | Primera venta con Colageno y Omega 3. |
| 70000002 | Luis Rios | Recompra anticipada de Colageno. |
| 70000003 | Carla Vega | Aun tiene producto y requiere reprogramacion. |
| 70000004 | Diego Flores | Tres intentos sin respuesta y envio a recuperacion. |
| 70000005 | Elena Paredes | Venta duplicada pendiente de aprobacion. |

## Cierre de Fase 0

- Historias de usuario y criterios de aceptacion documentados.
- Flujos y wireframes definidos.
- Modelo conceptual, reglas de integridad y datos ficticios preparados.
- Parametros iniciales definidos como configuracion editable.
- Listo para iniciar Fase 1: base tecnica y seguridad.
