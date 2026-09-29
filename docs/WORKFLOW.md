# Flujo Operativo Del CRM De Recompra

## Propósito

El CRM identifica clientes próximos a recomprar un producto, permite que los asesores registren la gestión y da a supervisión trazabilidad y mecanismos de reasignación.

## Roles

- **Asesor:** gestiona únicamente las alertas asignadas a su usuario, registra intentos de contacto y confirma recompras.
- **Supervisor:** consulta métricas, próximos vencimientos, registro de alertas y cola de recuperación; puede reasignar alertas y transferir carteras.
- **Administrador:** dispone de las funciones del supervisor y mantiene usuarios, productos, reglas, tipificaciones y parámetros operativos.

## Configuración Inicial

1. El administrador crea asesores activos, categorías, marcas y productos con precio unitario.
2. Define una regla de recompra vigente por producto: duración estimada y días de anticipación para alerta.
3. Configura tipificaciones de contacto. Cada una puede requerir nota, próxima acción o cierre.
4. Registra o importa clientes y sus ventas confirmadas. Cada venta conserva asesor, fecha, producto, cantidad y precio.

## Ciclo De Alertas

1. El proceso diario revisa las ventas confirmadas y crea una alerta por cada ítem cuyo ciclo de recompra llegó a la fecha correspondiente.
2. La alerta se asigna al responsable de cartera del cliente; si no existe, se asigna al asesor de la venta cuando está activo.
3. Las alertas recientes quedan `PENDIENTE`; las fuera de la ventana operativa pasan a `VENCIDO_NO_GESTIONADO` para recuperación.
4. La bandeja del asesor muestra sus alertas disponibles, priorizando seguimientos y vencimientos más urgentes.

## Gestión Del Asesor

1. El asesor abre una alerta desde **Mis alertas** y revisa cliente, producto, venta original, asesor vendedor y fecha prevista.
2. En una gestión regular selecciona tipificación, canal, nota y/o próxima acción según corresponda.
3. Una gestión que exige próximo contacto deja la alerta `REPROGRAMADO`; esta vuelve a la bandeja en la fecha programada.
4. Una recompra confirmada crea una venta enlazada a la alerta y la cierra como `RECOMPRA_LOGRADA`.
5. Si se compra otro producto, se registra la venta y la alerta original queda `COMPRA_OTRO_PRODUCTO`, disponible para recuperación.
6. Tipificaciones de cierre, no interesado, anulación y otros resultados dejan trazabilidad en el historial y actualizan el estado de alerta.

## Supervisión Y Reasignación

1. El dashboard muestra próximos vencimientos con cliente, producto, estado, intentos, asesor asignado y días transcurridos desde la venta original.
2. El supervisor usa **Registro de alertas** para auditar alertas abiertas, seguimientos y cierres con filtros e historial completo.
3. En **Cola de recuperación** filtra por cliente, producto, estado, última tipificación, días vencidos y días desde venta.
4. La cola muestra la antigüedad de venta junto al vencimiento, asesor actual y última gestión para tomar decisiones de reasignación.
5. Puede reasignar una alerta o seleccionar varias para una reasignación masiva. Cada operación exige motivo y queda registrada en historial y auditoría.
6. La transferencia de cartera actualiza el responsable del cliente y las alertas activas relacionadas.

## Métricas Del Dashboard

- Facturación total, ingresos de ventas regulares, ingresos exclusivos de recompra, unidades vendidas y ticket promedio.
- Top de productos por unidades y por facturación.
- Ranking de asesores ordenado por ingreso de recompras; los desempates usan recompras realizadas y alertas gestionadas.
- Gráfico circular que compara ingresos de ventas regulares contra recompras.

## Trazabilidad

- Cada intento conserva asesor, fecha, canal, tipificación, observación y próxima acción.
- Cada reasignación conserva asesor anterior, asesor nuevo, motivo, fecha y usuario ejecutor.
- Las operaciones relevantes escriben eventos de auditoría para alertas, ventas, clientes y asignaciones.

## Validación Técnica

```sh
cd backend && python -m pytest
cd frontend && npm run build
docker compose up --build --detach --wait
```

La API se documenta en `/docs` y el tablero se sirve desde el frontend configurado por Docker Compose.
