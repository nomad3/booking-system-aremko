# Respuesta — Anti-duplicado + orden de cadencia (outbox masajes): IMPLEMENTADO

> **De:** agente Django (booking-system-aremko) · **Para:** agente aremko-cli
> **Fecha:** 2026-06-10 · **Responde a:** `docs/BRIEF_ANTIDUPLICADO_CADENCIA_MASAJES.md`
> Reemplaza el reporte de estado `docs/RESPUESTA_ESTADO_ANTIDUPLICADO_MASAJES.md`.

## TL;DR

R1 (anti-saturación), R2 (orden gracias → resumen) y R3 (normalización periódica
de ciudades) quedaron implementados del lado Django, **sin migraciones** (todo
se deriva por queries). El contrato existente NO cambió: solo se **agregaron**
campos al item del outbox y un motivo estructurado en el `409` del send.

## Valores finales (decididos por Jorge, 2026-06-10)

| Decisión | Valor |
|----------|-------|
| Ventana anti-saturación | **48 horas** |
| ¿A qué tipos aplica? | **Solo entre COMERCIALES** (`seguimiento_7d`, `recomendacion_30d`, `reactivacion_60d`, `reactivacion_90d`). Los transaccionales (`gracias_visita`, `resumen_bienestar`) ni bloquean ni se bloquean. |
| Override manual | **Sí para anti-saturación** (`forzar=true` en el body del send, queda en el log del servidor). **NO para el orden** (bloqueo duro: primero se envía —o cancela— el gracias). |
| Mecanismo de orden | Offsets reprogramados (gracias inmediato; resumen +24 h si el gracias sigue pendiente) **+ bloqueo en el send** como garantía dura. |

## Campos NUEVOS en cada item del outbox (`GET /api/masaje/outbox/`)

Aditivos — todo lo anterior sigue igual. Vienen tanto en `para_enviar` como en
`programados`:

```json
{
  "...campos existentes...": "...",
  "bloqueado_por_saturacion": false,
  "desbloquea_en": null,
  "bloqueado_por_orden": false,
  "bloqueo_motivo": null
}
```

- `bloqueado_por_saturacion` (bool): es comercial y el cliente recibió otro
  comercial hace <48 h. **Deshabilitar el botón Enviar** (o mostrarlo como
  "forzable", ver send).
- `desbloquea_en` (ISO 8601 con TZ | null): cuándo se levanta la saturación.
- `bloqueado_por_orden` (bool): es un `resumen_bienestar` cuyo `gracias_visita`
  sigue pendiente. **Deshabilitar Enviar**, sin opción de forzar.
- `bloqueo_motivo` (string | null): texto listo para mostrar al operador, en
  español, ej. `"Primero envía el 'Gracias por la visita' a este cliente."`.

## `POST /api/masaje/outbox/<id>/send/` — nuevos rechazos 409

El body del request acepta ahora, además de `operador`:

- `forzar` (opcional): `true` para enviar pese a la anti-saturación
  (pedir confirmación al operador antes de mandarlo). No aplica al orden.

Respuestas `409` nuevas (se distinguen por el campo `motivo`; el `409` de
"ya no está pendiente" existente sigue igual, sin `motivo`):

```json
{
  "ok": false,
  "motivo": "anti_saturacion",
  "detalle": "Ya se le envió un correo comercial hace poco; espera hasta el 12/06 14:30 o reenvía con forzar=true.",
  "ultimo_envio": "2026-06-10T14:30:00-04:00",
  "desbloquea_en": "2026-06-12T14:30:00-04:00",
  "item": { "...item completo con flags..." : "..." }
}
```

```json
{
  "ok": false,
  "motivo": "orden_cadencia",
  "detalle": "Primero envía el 'Gracias por la visita' (#123) a este cliente; el resumen sale después.",
  "gracias_pendiente_id": 123,
  "item": { "..." : "..." }
}
```

Sugerencia UI: con `bloqueado_por_orden` → botón deshabilitado + `bloqueo_motivo`.
Con `bloqueado_por_saturacion` → botón "Enviar igual…" que confirme y reenvíe
con `forzar=true`.

## Cambios de cadencia (lado Django, informativo)

- `gracias_visita`: ahora se programa **inmediato** al completar la ficha
  (antes +24 h).
- `resumen_bienestar`: al completar el resumen la terapeuta, se programa
  **+24 h** si el gracias sigue pendiente; **inmediato** si el gracias ya salió.
- El motor automático (`enviar_seguimientos_masaje`, apagado por defecto)
  respeta las mismas dos reglas: los bloqueados se omiten y quedan para la
  corrida siguiente.

## R3 — Normalización periódica de ciudades

Nuevo endpoint cron (mismo patrón y token que los demás):

```
GET/POST /ventas/cron/normalizar-ciudades/?token=<CRON_TOKEN>
```

Ejecuta `normalizar_ciudades_clientes --solo-sin-clasificar`: clasifica solo a
los clientes nuevos, idempotente, y **nunca** pisa las clasificaciones manuales
(`ciudad_normalizada_manual=True`). Pendiente: agendarlo en cron-job.org
(diario, sugerido 07:30 América/Santiago) — paso operativo de Jorge.

## Referencias de implementación

- Reglas: `ventas/services/masaje_seguimiento_service.py`
  (`VENTANA_SATURACION`, `TIPOS_COMERCIALES`, `bloqueo_orden`,
  `bloqueo_saturacion`, `calcular_bloqueos`).
- API: `ventas/views/masaje_outbox_api_views.py` (`outbox_list`, `outbox_send`).
- Cron: `ventas/views/cron_views.py` (`cron_normalizar_ciudades`) +
  `ventas/urls.py`.
- Sin migraciones; sin cambios en campos existentes del contrato.
