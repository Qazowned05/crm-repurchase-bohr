# Auditoria Del Flujo Operativo

Fecha: 2026-09-28

## Alcance

Revision del flujo de venta, recompra, alertas, gestion, recuperacion, reportes, permisos y operacion. El estado descrito corresponde a la implementacion actual y a la base demo cargada localmente.

## Flujo Actual

1. Un asesor registra una venta confirmada para un cliente de su cartera.
2. Cada item guarda una instantanea de la regla vigente: duracion, dias de alerta y fecha estimada de recompra.
3. El proceso automatico genera una alerta en la fecha estimada y la asigna al asesor responsable.
4. El asesor gestiona la alerta con tipificacion padre e hija. Segun la configuracion, puede requerir nota, proxima accion o cierre automatico.
5. Las alertas con gestion pasan al Registro de alertas. Las reprogramadas siguen abiertas para seguimiento; las cerradas conservan trazabilidad.
6. Supervisor y administrador consultan la cola de recuperacion, reasignan alertas individuales o en bloque y revisan metricas.
7. Desde una alerta se puede registrar una recompra con el producto original, otros productos o ambos. Se crea una venta vinculada y se calcula el nuevo vencimiento de cada producto vendido.

## Reglas De Estado

| Estado | Significado operativo | Bandeja de asesor | Registro |
| --- | --- | --- | --- |
| `PENDIENTE` | Requiere gestion inicial | Si | No gestionada |
| `REPROGRAMADO` | Tiene siguiente accion pendiente | Si, mientras cumpla visibilidad | Si |
| `VENCIDO_NO_GESTIONADO` | Paso a recuperacion por vencimiento | No | Si |
| `CERRADO_POR_TIPIFICACION` | Cerrada por tipificacion configurada | No | Si |
| `RECOMPRA_LOGRADA` | Cerrada por venta de recompra | No | Si |

## Hallazgos Prioritarios

### Critico: Recompra De Producto Alternativo

Al elegir solamente otro producto en el modal de recompra, la alerta del producto original se marca como `RECOMPRA_LOGRADA`. Por tanto, desaparece de la bandeja, aunque el producto original no se haya comprado otra vez. La venta alternativa crea un nuevo ciclo solo para el producto nuevo.

Consecuencias:

- La recompra del producto original se registra como lograda sin evidencia de esa compra.
- El asesor no recibe un nuevo seguimiento para el producto original.
- La venta alternativa no se cuenta como recompra del producto original en el ranking, pero la alerta si se usa como conversion en algunos reportes.

Decision pendiente de negocio:

1. Recompra exacta: solo cerrar como `RECOMPRA_LOGRADA` si la venta contiene el producto original.
2. Conversion cruzada: cerrar con un estado distinto, por ejemplo `COMPRA_ALTERNATIVA`, conservando la alerta original abierta o cerrandola con una regla comercial explicitamente definida.

Recomendacion: aplicar la opcion 1 como comportamiento por defecto. La opcion 2 debe ser una politica configurable y tener metricas separadas.

### Alto: Metricas Inconsistentes Para Recompra Directa

Una recompra registrada directamente no crea un intento de contacto. El indicador de recompras usa alertas `RECOMPRA_LOGRADA`, mientras el denominador de alertas atendidas usa intentos de contacto. Esto puede producir tasas superiores a 100% y rankings que no coinciden entre si.

Correccion propuesta: registrar una gestion de sistema al confirmar la recompra, o calcular atendidas, conversion y ranking a partir de un unico evento de recompra atribuido a la alerta.

### Alto: Recuperacion No Reactiva Correctamente La Alerta

Reasignar una alerta de recuperacion no reinicia los criterios que la dejaron fuera de la bandeja, como cantidad maxima de intentos o antiguedad. La alerta puede continuar excluida del asesor y volver a aparecer de inmediato en recuperacion.

Correccion propuesta: definir un estado explicito de recuperacion y restablecer o versionar los criterios operativos al reasignar.

### Alto: Recordatorios Configurados No Se Ejecutan

Las reglas almacenan dias de alerta, por ejemplo 14 y 7 dias antes, pero actualmente se crea una sola alerta en la fecha estimada de recompra. La restriccion actual impide multiples recordatorios por item.

Correccion propuesta: modelar cada recordatorio por `(sale_item_id, alert_date)`, conservar una politica de cancelacion al vender y separar recordatorio preventivo de alerta vencida.

### Alto: Borrado Permanente De Ventas Elimina Evidencia Operativa

La eliminacion administrativa puede borrar ventas, alertas, intentos y asignaciones vinculadas. Solo queda una instantanea parcial en auditoria.

Correccion propuesta: sustituir el borrado de ventas confirmadas por anulacion/correccion inmutable. Si se mantiene el borrado, almacenar una instantanea completa de las entidades dependientes y aplicar una politica de retencion.

## Hallazgos Medios

- La recompra desde alerta cierra la alerta origen, pero no necesariamente otras alertas activas de productos incluidos en la nueva venta. Puede dejar seguimientos duplicados.
- La creacion generica de venta y el endpoint de recompra aplican reglas distintas para atribuir `source_alert_id`.
- La paginacion responde paginas, pero varios endpoints cargan todos los registros antes de paginar en memoria. Debe paginarse en SQL con orden estable y conteo.
- Los selectores de venta cargan solo los primeros 200 clientes y productos; se requiere busqueda remota para una base mayor.
- La interfaz no expone transferencia de cartera, historial de asignacion, configuracion operativa de alertas, anulacion/reemplazo de venta ni revision de duplicados, aunque parte de la API existe.
- La administracion de usuarios no permite activar/desactivar correctamente y solicita contrasena al editar datos no sensibles.
- Errores de carga, paginacion y algunos modales no se muestran de forma consistente.
- Los modales necesitan completar accesibilidad: foco inicial, trampa de foco, Escape, restauracion de foco y bloqueo de cierre accidental durante una operacion.

## Riesgos Operativos Y De Calidad

- El scheduler de alertas es un hilo local por proceso. En multiples replicas puede ejecutarse en paralelo; requiere bloqueo distribuido o trabajo programado unico.
- Las migraciones se ejecutan al iniciar cada backend. Produccion requiere un trabajo de migracion unico y bloqueado.
- El reinicio demo conserva usuarios pero borra datos operativos, catalogo, configuracion y auditoria. Debe usarse solo en entornos de prueba, con respaldo validado.
- No hay pruebas de interfaz ni pruebas automatizadas de PostgreSQL/Alembic/Docker. La suite actual cubre backend principalmente con SQLite.

## Capacidades Verificadas

- Reglas de recompra efectivas por producto y almacenadas como instantanea en cada venta.
- Alertas y gestiones con permisos por rol y por asesor asignado.
- Tipificaciones jerarquicas con requisitos configurables de nota, siguiente accion y cierre.
- Registro persistente de alertas gestionadas y cierre por tipificacion o recompra.
- Asignacion individual y masiva en recuperacion con motivo e historial.
- Recompra idempotente mediante bloqueo de alerta y restriccion unica de venta origen.
- Paginacion visual compartida y datos demo distribuidos entre los tres asesores.

## Orden Recomendado De Implementacion

1. Definir y corregir la politica de recompra alternativa, incluyendo estados y metricas.
2. Unificar el evento de recompra para alertas, ventas, historial y dashboard.
3. Corregir reactivacion de alertas reasignadas en recuperacion.
4. Implementar recordatorios preventivos configurados por regla.
5. Sustituir borrado permanente de ventas confirmadas por anulacion auditable.
6. Mover paginacion a consultas SQL y agregar busqueda remota a selectores grandes.
7. Completar operaciones administrativas faltantes y manejo uniforme de errores.
8. Fortalecer scheduler, despliegue y cobertura de pruebas.
