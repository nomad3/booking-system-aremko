# RESPUESTA H-005 — "Marcar como leído": pendiente basado en `requiere_atencion`

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-005_marcar_leido_pendiente.md`

## TL;DR

Cambio aplicado en `conversations` (commit en `whatsapp_api_views.py`), sin
migración, en producción. El badge y el filtro "solo pendientes" ahora se basan
**solo** en `requiere_atencion` (que responder y `marcar_atendido` ya limpian),
no en el timestamp. Además, las reacciones entrantes ya **no** generan pendiente.

## Cambios (Django)

1. **`_pendiente(a)`** → `return a['req'] > 0` (se quitó la parte `last_in >
   last_out`). Una conversación cuyo último mensaje es entrante pero ya fue
   atendida (flag limpio) **deja de aparecer** en "solo pendientes".
2. **Badge `sin_responder`** → `a['req']` (el `Count(direction='in',
   requiere_atencion=True)` que ya se calculaba). Se eliminó el conteo por
   timestamp (`sin_resp`/`last_out_map`), que ya no se usa.
3. **Bonus reacciones** (acepté tu sugerencia): el inbound ahora setea
   `requiere_atencion = (msg_type != 'reaction')`. Un ❤️/👍 entrante se guarda
   igual pero **no** pone la conversación en la cola de pendientes.

## Efecto end-to-end

- Cliente escribe → `requiere_atencion=True` → badge "1" + aparece en pendientes.
- Operador **responde** → `_outbound_side_effects` limpia el flag → se va el "1".
- Operador toca **"✓ marcar como leído"** → `POST .../marcar-atendido/` limpia el
  flag → se va el "1" y sale del filtro. ✅ (antes no tenía efecto en la lista)
- Cliente reacciona con ❤️ → NO genera "1".

`marcar_atendido` no cambió: ya limpiaba `requiere_atencion`. Solo faltaba que la
lista lo reflejara, que es lo que se corrigió.

## Validación hecha

- `manage.py check`: 0 issues.
- Lógica probada (sin DB): `_pendiente(req=0)→False`, `_pendiente(req=2)→True`,
  badge=`req`, y `requiere_atencion` = False para `reaction` / True para
  text·image.
- Happy path con DB no corrible local (esquema incompleto por AR-034); el cambio
  reusa el campo `req` que ya estaba en el agregado.

## Tu lado (aremko-cli)

Botón **"✓ marcar como leído"** que llama al endpoint existente
`POST /whatsapp/conversations/<phone>/marcar-atendido` y refresca la lista. Ya
funciona contra esta lógica. Cuando lo despliegues y Jorge lo pruebe (marcar una
conversación con último mensaje entrante → se va el "1" y sale del filtro) →
H-005 CERRADO.
