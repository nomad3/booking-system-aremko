# BRIEF H-029 — Flujo de carrito de reservas de Luna (diseño completo)

**Pedido de Jorge (2026-06-18), diseñado con aremko-cli.** Evoluciona H-028 (que creaba
reservas de tina sueltas) al flujo real: Luna conversa como un **CARRITO** y agenda
una reserva con uno o varios servicios. Construir **con calma y bien probado** — es el
corazón de que Luna venda sin errores. Reusa la Luna API existente (`luna_api_views.py`).

## Principio rector
**Una conversación = un carrito = una reserva** (`VentaReserva`). Los servicios se
ACUMULAN; **un total, un pago, un resumen**. El cliente entra por cualquier servicio
(tina/masaje/cabaña) y agrega los demás. NO crear una reserva por servicio ni cobrar
por separado.

## Contexto del flujo manual actual (respetarlo)
- Deborah crea la reserva (queda `estado_pago=pendiente`), envía el resumen con datos de
  transferencia, el cliente paga cuando puede (a veces días), Deborah **registra el pago
  a mano en el admin** y el sistema **dispara solo el mail de "reserva pagada"**.
- ⇒ **Luna NO toca el pago.** Llega hasta crear la reserva + enviar el resumen. El registro
  del pago sigue siendo manual de Deborah y el mail de pagada ya existe. Luna se integra,
  no reemplaza ese tramo.

## FASE 1 — Recolección de datos (arregla el "error interno" actual) 🔴 PRIORITARIO
Hoy Luna salta a `preparar_reserva` sin juntar nombre/email/RUT → error. Falta el guion:
- **Teléfono:** WhatsApp → ya lo tenemos (NO pedirlo). Instagram/Messenger → Luna lo PIDE
  (el external_id es IGSID/PSID, no sirve como teléfono).
- **`verificar_cliente` como HERRAMIENTA del agente** (el endpoint `/api/luna/cliente/` existe
  pero el agente no lo llama): con el teléfono → `{existe, nombre, faltan:[...]}`.
  - existe y completo → no pedir nada.
  - existe pero falta email/comuna → pedir SOLO eso.
  - nuevo → pedir nombre + email + comuna + RUT.
- SOLO con todos los datos requeridos + confirmación del cliente → `preparar_reserva`.
- Robustez: si falta un dato, `preparar_reserva` devuelve `{success:false, falta:[...]}`
  (NO excepción) → Luna pide el dato, no deriva a persona.
- **external_id (conversación) ≠ teléfono (cliente):** en IG/Messenger la propuesta se keyea
  por IGSID/PSID (para el banner), pero `cliente.telefono` = el que Luna pidió. NO usar el
  IGSID como teléfono. (En las llamadas a `_producir_borrador` de inbox_omnicanal pasar
  `phone=external_id, canal=...` — hoy faltan en IG/Messenger.)

## FASE 2 — El carrito (multi-servicio)
- **`CarritoReserva`** (tabla propia, app aislada, persistente por conversación `(canal, external_id)`).
  La web sigue con su carrito de sesión; **no compiten** porque ambos confluyen en la misma
  `VentaReserva`/disponibilidad (la disponibilidad cuenta TODAS las reservas creadas).
- Tools del agente: agregar servicio al carrito, quitar, ver carrito. Cada servicio con
  fecha/hora/personas; total parcial con descuento de combo (`PackDescuentoService`).
- **Cross-sell sutil tras cada agregado** (SIN presionar; **no insistir si ya dijo que no**):
  tina→ofrece masaje/cabaña; masaje→tina/alojamiento; cabaña→tina/masaje.
- **Checkout** (cliente dice "quiero pagar/reservar") → recolección de datos (Fase 1) →
  resumen del carrito → confirma → botón "Crear reserva" (Deborah aprueba) → UNA `VentaReserva`
  con todos los servicios (re-verifica disponibilidad, idempotente, packs) → resumen
  (nº+banco+mail+foto, total del carrito) → Luna lo envía.
- **Agregar después de creada:** `agregar_servicios_reserva` a la MISMA reserva → regenera resumen, un pago.

## FASE 3 — Holds + expiración
- Al crear la reserva (pendiente), los slots quedan "tomados" (disponibilidad ya excluye
  reservas creadas — vale web + Luna).
- **Cron diario 23:00** libera las reservas `pendiente` impagas, EXCEPTO:
  - las creadas entre **21:00 y 23:00** → viven hasta las **23:00 del día siguiente** (grace).
  - las que Deborah marcó como **"esperando pago"** (flag nuevo en `VentaReserva`, ej.
    `eximir_liberacion`, editable en admin/aremko-cli) → NO se liberan.
- Mensaje al cliente en el resumen: *"Tu reserva se mantiene hasta las 23:00 de hoy; si no
  se paga, se libera."*
- (Automatiza la página manual `eliminar_reservas_no_pagadas`.)

## FASE 4 — Coordinación de combos (disponibilidad)
- tina+masaje el mismo día (orden/horarios — H-011 Fase B) y cabaña+tina/masaje (tina más
  tarde ≥16:00, masaje antes si hay alojamiento — reglas ya definidas, ver memoria cabaña nivel 2/3).
- cabaña multi-noche ya existe (H-027).

## Reparto
- **Django:** `CarritoReserva` + flag `eximir_liberacion` + tools (`verificar_cliente`,
  carrito add/remove/ver, checkout) + prompt del guion (recolección + cross-sell) + cron 23:00
  + coordinación combos. Reusa la Luna API (`luna_api_views.py`) ya existente.
- **aremko-cli:** ya tiene botón "Crear reserva" + traer resumen (commit f23f98c). Sumar lo que
  el carrito/expiración necesiten mostrar (ej. flag "esperando pago" en la ficha) cuando se defina.

## Decisiones cerradas por Jorge
- Carrito propio de Luna (no la propuesta directa) que al checkout pasa a reserva.
- Cross-sell sutil, no insistir si declinó.
- Cron 23:00 libera **todas menos las que Deborah exime**; grace 21:00–23:00 → +1 día.
- Pago manual (Deborah registra → mail auto de "pagada" ya existe); Luna no toca el pago.
