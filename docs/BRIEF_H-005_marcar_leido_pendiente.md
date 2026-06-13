# BRIEF H-005 — "Marcar como leído": que el pendiente se base en `requiere_atencion`, no en timestamp

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (lógica de la lista) + aremko-cli (botón). Este brief cubre **Django**.
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO

## Necesidad (de Jorge)

Cuando el cliente manda la última frase y **ya no hay nada que responder**, la conversación
queda con el badge **"1"** y sigue apareciendo en el filtro **"Solo las que esperan respuesta"**.
Jorge quiere un **botón "marcar como leído"** que la saque de pendientes (quite el "1" y la
saque del filtro), aunque el último mensaje sea entrante.

## Diagnóstico (desde aremko-cli)

- Ya existe `marcar_atendido` (`whatsapp_api_views.py` ~L569) que limpia `requiere_atencion`
  de los entrantes, y **responder ya lo limpia** (`_outbound_side_effects`).
- **PERO** la vista `conversations` (L468+) calcula el estado por **timestamp**, no por ese flag:
  - `_pendiente(a)` (L503) = `last_in > last_out` **OR** `req > 0` → el `last_in > last_out`
    mantiene la conversación pendiente aunque se limpie el flag.
  - `sin_responder` (badge, L520-534) = conteo de entrantes con `timestamp > last_out` →
    tampoco mira el flag.
- Resultado: marcar-atendido (o el botón nuevo) **no quita el "1" ni saca del filtro** hoy.

## Pedido (Django) — cambio chico en `conversations`

Que el estado se base en `requiere_atencion` (que responder y marcar-atendido **ya** limpian):
1. **Badge:** `sin_responder` = `req` (el `Count(... filter=Q(direction='in', requiere_atencion=True))`
   que ya se calcula en L499) en vez del conteo por timestamp.
2. **Filtro:** `_pendiente(a)` = `a['req'] > 0` (quitar la parte de `last_in > last_out`).

Con eso: cliente escribe → `requiere_atencion=True` → "1"; responde **o** marca-leído → flag
limpio → se va el "1" y sale de "solo pendientes". (El endpoint `marcar_atendido` ya hace el
trabajo; solo falta que la lista lo refleje.)

### Consideración opcional (reacciones)
Recién (aremko-cli `d293611`) las reacciones entrantes (`type="reaction"`) se guardan como
mensaje entrante → hoy setean `requiere_atencion=True` y generarían un "1" por un ❤️. Evaluar
**no** marcar `requiere_atencion` para `type='reaction'` (una reacción normalmente no pide
respuesta). Opcional, lo dejo a tu criterio.

## Lado aremko-cli (lo hace este agente)

- Botón **"✓ marcar como leído"** en el encabezado/lista de la conversación que llama al
  endpoint existente `POST /whatsapp/conversations/<phone>/marcar-atendido` y refresca.
- Lo despliego cuando confirmes el cambio de la lista (si no, el botón no tendría efecto visible).

## Aceptación

- Con una conversación cuyo último mensaje es entrante: tocar "marcar como leído" quita el "1"
  y la saca del filtro "solo pendientes". Responder produce el mismo efecto.

## Punteros (Django)

- `ventas/views/whatsapp_api_views.py`: `conversations` (L468), `_pendiente` (L503),
  `sin_resp` (L520-534), `req` (L499), `marcar_atendido` (L569), `_outbound_side_effects`.
