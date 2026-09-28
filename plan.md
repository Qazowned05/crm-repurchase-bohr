# Plan de desarrollo por fases

Este plan convierte la especificacion funcional en entregas tecnicas pequenas y verificables. Cada fase debe cerrar con pruebas automatizadas y una demostracion usando datos ficticios.

## Fase 0 - Definicion final

**Objetivo:** cerrar los parametros operativos antes de programar reglas de negocio.

- Confirmar historias de usuario y criterios de aceptacion.
- Definir wireframes de login, clientes, ventas, bandeja de alertas, importacion, supervision y reportes.
- Definir valores iniciales configurables: intentos maximos, dias entre intentos, ventana activa, vencimiento y escalamiento a recuperacion.
- Validar el catalogo de tipificacion y los canales de captacion `TV`, `DIGITAL` y `OTROS`.
- Aprobar el modelo de datos, estados, permisos y plantillas Excel.

**Cierre:** reglas y wireframes aprobados; datos ficticios de prueba preparados.

## Fase 1 - Base tecnica y seguridad

**Objetivo:** disponer de una aplicacion ejecutable, segura y migrable.

- Crear repositorio con `frontend` y `backend`.
- Configurar Docker Compose, PostgreSQL, variables de entorno y Alembic.
- Crear la estructura modular de FastAPI y React con TypeScript.
- Implementar autenticacion, contrasenas cifradas, JWT, recuperacion de contrasena y control de roles.
- Crear auditoria base, manejo de errores, validacion de entradas y pruebas iniciales.
- Crear administrador inicial mediante un procedimiento seguro.

**Cierre:** login funcional, rutas protegidas por rol, migraciones reproducibles y pruebas de autenticacion aprobadas.

## Fase 2 - Usuarios, clientes y productos

**Objetivo:** administrar la base comercial y las reglas de recompra.

- CRUD de usuarios, activacion, desactivacion y roles.
- CRUD de clientes, busqueda por DNI, validacion de duplicados y responsable de cartera.
- CRUD de productos con codigo unico, estado y categoria.
- Configuracion versionada de reglas por producto: duracion, dias de alerta, vigencia y aprobacion medica.
- Auditoria de cambios en usuarios, clientes, productos y reglas.
- Pantallas y permisos correspondientes.

**Cierre:** un asesor encuentra o crea un cliente; supervisor y administrador configuran productos y reglas sin alterar historicos.

## Fase 3 - Importacion masiva

**Objetivo:** cargar clientes y productos de forma controlada.

- Generar plantillas descargables `.xlsx` con instrucciones y ejemplos ficticios.
- Validar encabezados, formato, campos obligatorios, tamanos, macros, duplicados y conflictos.
- Mostrar vista previa de filas nuevas, actualizables y rechazadas.
- Implementar importacion atomica, archivo de errores descargable y trazabilidad por lote.
- Permitir reasignacion de cartera explicita por importacion.
- Crear nuevas reglas versionadas al importar cambios de configuracion de productos.

**Cierre:** supervisor importa clientes y productos validos; un archivo con errores no modifica datos.

## Fase 4 - Ventas y recompra

**Objetivo:** registrar ventas confiables y construir el historial comercial.

- Registrar ventas con uno o varios productos, cantidad y observacion.
- Solicitar canal de captacion obligatorio en la primera venta confirmada: `TV`, `DIGITAL` u `OTROS` con descripcion.
- Guardar la copia de la regla de recompra en cada producto vendido.
- Clasificar cada producto vendido como `COMPRA` o `RECOMPRA` y relacionar la recompra con la venta anterior.
- Detectar ventas duplicadas y exigir aprobacion para confirmar excepciones.
- Implementar anulación auditada, venta de reemplazo y recalculo de ciclos afectados.
- Manejar ventas registradas con fecha pasada.

**Cierre:** ventas confirmadas generan historial correcto; anulaciones y duplicados no generan metricas ni alertas incorrectas.

## Fase 5 - Alertas y tipificacion

**Objetivo:** entregar una bandeja operativa de recompras para asesores.

- Crear proceso diario idempotente de generacion de alertas por producto vendido.
- Aplicar asignacion al responsable actual del cliente y enviar excepciones a la cola de recuperacion.
- Implementar estados, vencimiento configurable, reprogramacion, reasignacion y cierre por recompra o anulacion.
- Garantizar que una recompra cierre la alerta de origen y cancele las demas alertas activas del mismo cliente-producto.
- Implementar bandeja priorizada: vencidas recientes, hoy, proximas y reprogramadas.
- Registrar intentos de contacto con canal usado, resultado tipificado, nota y proxima accion.
- Implementar el catalogo de tipificacion: recompra, aun tiene producto, solicita seguimiento, sin respuesta, no interesado, datos incorrectos y otro.

**Cierre:** el flujo completo funciona: cliente -> venta -> alerta -> contacto -> recompra o cierre.

## Fase 6 - Supervision y reportes

**Objetivo:** permitir control de cartera, recuperacion y medicion comercial.

- Transferir cartera y alertas activas entre asesores con historial de asignacion.
- Implementar cola de recuperacion para usuarios inactivos, alertas abandonadas y datos incorrectos.
- Construir indicadores de alertas, contacto, recompra, ventas, productos, asesores y canal de captacion.
- Separar en reportes asesor que vendio, responsable de cartera y asesor que gestiono la alerta.
- Calcular promedio de dias entre compras.
- Crear filtros y exportacion a CSV o Excel.

**Cierre:** supervisor puede reasignar trabajo, recuperar seguimientos y exportar indicadores consistentes.

## Fase 7 - Calidad, piloto y produccion

**Objetivo:** validar el sistema con seguridad antes del uso real.

- Completar pruebas unitarias, integracion, interfaz y end-to-end.
- Ejecutar pruebas de permisos, concurrencia, duplicados, anulación, importacion y proceso diario de alertas.
- Configurar staging, HTTPS, respaldos, restauracion de respaldo, monitoreo y registro de errores.
- Ejecutar piloto con usuarios seleccionados y datos controlados.
- Corregir incidencias, capacitar usuarios y preparar despliegue productivo.

**Cierre:** todas las pruebas criticas pasan en staging, existe respaldo verificable y el piloto es aprobado.

## Orden de inicio

1. Completar Fase 0.
2. Implementar Fase 1 y no avanzar sin migraciones, autenticacion y pruebas base.
3. Continuar las fases 2 a 6 en orden, integrando y probando cada una antes de iniciar la siguiente.
4. Desplegar solo despues de completar la Fase 7.
