# H-060 — Luna agrega servicios/productos a una reserva YA CREADA (Gate de Deborah)

## Objetivo

Hoy, cuando un cliente aprueba una cotización con Luna, se crea una `VentaReserva` real
(posiblemente ya pagada o parcial). Si el mismo cliente escribe más tarde (mismo día o al día
siguiente) pidiendo sumar un servicio o producto a esa reserva, la ÚNICA forma de hacerlo era
que Jorge/Deborah editara la reserva a mano en el admin de Django. Esta feature le da a Luna
una forma conversacional de ofrecer esto, sin saltarse la aprobación de Deborah.

## Flujo end-to-end

1. El cliente escribe algo como "quiero agregar un masaje a mi reserva del sábado".
2. Luna llama `buscar_reservas_cliente` (nueva tool, solo lectura) → lista las reservas
   ELEGIBLES de ese teléfono (no canceladas, con fecha vigente o reciente). Si hay una sola,
   sigue directo; si hay varias, le pregunta al cliente cuál es (por fecha/resumen, nunca por
   ID interno).
3. Con la reserva identificada, Luna llama `agregar_servicio_a_reserva_existente` o
   `agregar_producto_a_reserva_existente` (nuevas tools) → esto NO modifica la reserva: crea
   una `PropuestaReserva` con `reserva_existente_id` seteado, `estado='pendiente'` — **mismo
   Gate de Deborah que una reserva nueva**.
4. aremko-cli muestra el mismo botón "Crear reserva" que ya usa para reservas nuevas (la
   `PropuestaReserva` es la misma tabla/mecanismo).
5. Deborah aprueba → `crear_reserva(propuesta_id)` detecta `reserva_existente_id` y, en vez de
   crear una `VentaReserva` nueva, agrega los servicios/productos a la reserva #X ya real
   (`agregar_items_a_reserva`), recalcula total/saldo/estado_pago correctamente, y marca la
   propuesta como `creada` (con `reserva_id` = la reserva a la que se agregó, para que el guard
   de doble-aprobación siga funcionando).

## Decisión de arquitectura confirmada por Jorge

Jorge confirmó explícitamente (pregunta directa, no asumido) que el flujo debe pasar por su
aprobación antes de aplicarse — la alternativa (Luna escribe directo sobre la reserva real) fue
descartada. Esto reusa el 100% del mecanismo "Gate de Deborah" que ya existe para reservas
nuevas (`PropuestaReserva` + botón "Crear reserva" en aremko-cli), sin inventar un flujo
paralelo.

## Bugs encontrados y corregidos (no solo una feature nueva)

Investigando el endpoint existente `agregar_servicios_reserva` (construido en el refactor de
carrito H-029, pero nunca conectado a ninguna tool de Luna — solo lo llamaba un script de
test), encontramos y corregimos 2 bugs reales:

1. **`estado_pago` nunca bajaba de 'pagado' a 'parcial'**: el endpoint recalculaba
   `total`/`saldo_pendiente` a mano pero nunca llamaba a `venta_reserva.actualizar_saldo()` —
   si una reserva ya pagada recibía un servicio nuevo sin pagar, el saldo pendiente subía pero
   el estado se quedaba pegado en "Pagada". Exactamente el escenario que motivó este pedido.
2. **El total recalculado perdía los productos existentes**: al recalcular `total`, el código
   solo sumaba `ReservaServicio` — cualquier `ReservaProducto` que la reserva ya tuviera
   (de la creación original) se perdía del total si después se llamaba este endpoint para
   agregar un servicio.

Ambos se corrigieron en una función compartida nueva (`ventas/services/
reserva_addition_service.py::agregar_items_a_reserva`), reusada tanto por el endpoint HTTP
existente (`agregar_servicios_reserva`, ahora también soporta productos) como por la
aprobación de una propuesta de adición.

## Piezas construidas

### A. Django (agente Django) — ✅ COMPLETO
1. `whatsapp_agent/models.py`: campo nuevo `PropuestaReserva.reserva_existente_id` +
   migración `0010` (app aislada, drift-safe — sin necesidad de migración escrita a mano como
   sí requieren `ventas`/`control_gestion` por AR-034).
2. `whatsapp_agent/reservas_existentes.py` (nuevo): lógica pura de elegibilidad/resumen,
   testeada sin DB en `whatsapp_agent/tests/test_logic.py`.
3. `whatsapp_agent/reserva_service.py`: `buscar_reservas_elegibles(telefono)` (fuente única
   para el endpoint HTTP y la tool de Luna) + `preparar_adicion_a_reserva(...)` (crea la
   propuesta de adición, reusa `recalcular_propuesta` para el delta de precio).
4. `ventas/services/reserva_addition_service.py` (nuevo): `agregar_items_a_reserva(...)` —
   fuente única con el fix de los 2 bugs de arriba.
5. `ventas/views/luna_api_views.py`: nuevo endpoint `GET /api/luna/reservas/buscar/`
   (descubrimiento); `crear_reserva` extendido para branch-ear a
   `_aprobar_adicion_a_reserva_existente` cuando la propuesta trae `reserva_existente_id`
   (con el mismo guard de concurrencia `select_for_update` que ya protege la creación de
   reservas nuevas); `agregar_servicios_reserva` ahora delega a la función compartida y
   soporta `productos` en el body (antes solo `servicios`).
6. `whatsapp_agent/agent.py`: 3 tools nuevas (`buscar_reservas_cliente`,
   `agregar_servicio_a_reserva_existente`, `agregar_producto_a_reserva_existente`) — dos tools
   separadas para servicio/producto (no una combinada), mismo criterio que
   `agregar_servicio_carrito`/`agregar_producto_carrito` en el carrito.
7. `whatsapp_agent/prompt.py`: sección nueva "3c. AGREGAR A UNA RESERVA YA HECHA" +
   `PROMPT_VERSION` subida.
8. Tests puros nuevos en `whatsapp_agent/tests/test_logic.py` (elegibilidad/resumen/orden) +
   management command de solo lectura `diagnosticar_adicion_reserva` (con modo de simulación
   revertida para probar el fix del bug contra una reserva real sin persistir nada).

### B. aremko-cli (agente aremko-cli) — ⬜ PENDIENTE (handoff, no implementado en este repo)
El serializer que arma `propuesta_reserva` para el cajón de cotización vive DENTRO de este
mismo repo Django (`inbox_omnicanal/views.py::_propuesta_reserva`, NO en el repo de
aremko-cli) — ya se le sumó el campo `reserva_existente_id` (null si es una reserva nueva).
Lo que SÍ queda pendiente del lado aremko-cli:
1. Leer `reserva_existente_id` en el cajón de cotización: si viene seteado, mostrar "esto se
   agrega a la Reserva RES-X" en vez de "esto crea una reserva nueva" (mismo botón "Crear
   reserva", sin cambio de endpoint ni de contrato de request).
2. Leer `agregado: true` en la respuesta de `POST /api/luna/reservas/create/` para mostrar el
   mensaje de éxito correcto ("se agregó a la reserva" vs. "reserva creada") — el resto de la
   respuesta (`reserva.id/numero/total/estado_pago`) tiene la misma forma de siempre.

## Reuso confirmado (no reinventado)
- `PropuestaReserva` + el mecanismo "Gate de Deborah" completo (aprobación vía aremko-cli,
  botón "Crear reserva", `POST /api/luna/reservas/create/`) — sin tabla ni flujo paralelo.
- `recalcular_propuesta()` (fuente única de cálculo de precio/descuento, ya usada por
  `preparar_reserva`/`editar_propuesta`) — para el delta de precio de la propuesta de adición.
- El patrón de 3 tablas para productos (Comanda + DetalleComanda + ReservaProducto con
  `fecha_entrega=NULL`) ya usado por `crear_reserva` — replicado, no reinventado.
- El guard de concurrencia `select_for_update()` de `crear_reserva` (caso real 6169/6170) —
  mismo criterio aplicado a la aprobación de una adición.

## Estado
- **Django**: ✅ COMPLETO — deployado y con migración aplicada en prod.
- **aremko-cli**: ⬜ PENDIENTE (B1–B2 de arriba) — el botón "Crear reserva" funciona igual sin
  este cambio (aprueba y aplica la adición correctamente), pero el cajón mostraría el mismo
  texto genérico de "reserva nueva" hasta que se lea `reserva_existente_id`/`agregado`.
