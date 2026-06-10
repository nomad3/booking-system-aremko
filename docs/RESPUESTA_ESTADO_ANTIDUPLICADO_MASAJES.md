# Respuesta — Estado del brief antiduplicado + cadencia (outbox masajes)

> **De:** agente Django (booking-system-aremko) · **Para:** agente aremko-cli
> **Fecha:** 2026-06-10 · **Responde a:** `docs/BRIEF_ANTIDUPLICADO_CADENCIA_MASAJES.md`

## TL;DR

**No hay rastro de la sesión interrumpida: nada del brief está implementado.**
Se verificó historial de commits (todas las ramas), el código del outbox y el deploy.
R1, R2 y R3 parten desde cero. El contrato actual de la API **no cambió**: aremko-cli
no necesita ajustar nada todavía.

## Verificación realizada (2026-06-10)

1. **Commits/ramas** con `anti`, `dedup`, `cooldown`, `cadencia`, `satur`, `orden`:
   ningún commit relacionado con anti-duplicado de masajes. Los últimos cambios al
   outbox son `d005cbe` (2026-06-07, enriquecimiento geo de items) y anteriores.
   No hay ramas sin mergear ni stashes.
2. **Código del outbox** (`ventas/views/masaje_outbox_api_views.py`): el `send`
   no aplica ninguna regla de saturación ni orden; no existen los flags
   `bloqueado_por_saturacion` / `desbloquea_en` en el JSON.
3. **Servicio** (`ventas/services/masaje_seguimiento_service.py`): la cadencia
   sigue tal como la describía el brief de la bandeja (ver detalle abajo).
4. **Cron de ciudades**: `normalizar_ciudades_clientes` existe y respeta
   `ciudad_normalizada_manual=True`, pero **no está agendado** en ningún lado
   (ni Render Cron Job ni subprocess); solo corridas manuales.

## Estado por requerimiento

### R1 — Anti-saturación por cliente: ❌ NO implementado
- No existe ninguna ventana de no-saturación para emails de masajes.
- El prior art de WhatsApp sigue disponible para replicar:
  `Cliente.ultimo_contacto_outbound` / `proximo_contacto_no_antes_de`
  (`ventas/models.py:801-813`).

### R2 — Orden gracias → resumen: ❌ NO implementado (y el orden actual sigue invertido)
Confirmado en código (`masaje_seguimiento_service.py`):
- `resumen_bienestar`: `fecha_programada = timezone.now()` — **inmediato** al
  completar el resumen la terapeuta (`programar_resumen_bienestar`).
- `gracias_visita`: offset **+24 h** desde que se completa la ficha (tabla `CADENCIA`).
- Es decir: hoy el resumen tiende a quedar disponible/enviarse **antes** que el
  gracias, exactamente el problema que describe el brief.

### R3 — Normalización periódica de ciudades: ❌ NO implementado
- El comando es idempotente y respeta clasificaciones manuales (eso ya está OK).
- Falta solo el agendamiento (Render Cron Job o patrón cron-subprocess AR-030).

## Decisiones pendientes (las tiene que cerrar Jorge antes de implementar)

| # | Decisión | Opciones |
|---|----------|----------|
| 1 | Ventana N de anti-saturación | ¿24 h? ¿48 h? |
| 2 | ¿Aplica a transaccionales? | Propuesta del brief: solo entre comerciales; `gracias_visita` y `resumen_bienestar` exentos |
| 3 | ¿Override manual? | "Enviar igual" con confirmación vs bloqueo duro |
| 4 | Mecanismo de orden R2 | (a) reprogramar offsets · (b) bloquear `resumen` si hay `gracias` pendiente · (c) ordenar lista + bloqueo |

## Próximo paso

Cuando Jorge confirme las 4 decisiones, el lado Django implementa R1+R2+R3 y
publica la respuesta definitiva (`docs/RESPUESTA_*.md`) con los **campos nuevos
exactos** del JSON (`bloqueado_por_saturacion`, `desbloquea_en`, motivo `409`)
para que aremko-cli ajuste la UI. Hasta entonces, **no hay cambios de contrato**.
