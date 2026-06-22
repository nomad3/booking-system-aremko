# H-038 — Luna Interna · Fase 2: avisos de operación al recepcionista (canal saliente)

**Pedido por:** Jorge, 2026-06-22 · **Plan:** `docs/PLAN_LUNA_INTERNA.md` · Sigue a H-037 (Fase 0).
**Contexto:** Jorge está cubriendo recepción "hasta nuevo aviso" y necesita que le lleguen por
WhatsApp los avisos de cada tarea operativa apenas se generan, para verificar que se cumplan.

## Qué es
control_gestion YA crea tareas automáticas desde las reservas (al hacer check-in: 1 tarea de
Recepción + 1 de Operación por servicio, ej. "Preparar servicio – tina" con checklist y hora límite).
Esta fase agrega el **puente a WhatsApp**: cuando se crea una tarea de Recepción/Operación → aviso al
recepcionista de turno.

## Ya hecho — Django (commit 0029459)
- `PersonalOperativo.recibe_avisos_operacion` = marca al "recepcionista de turno" (Jorge lo activa en su número).
- Signal post_save sobre `control_gestion.Task` (swimlanes RX/OPS) → encola un aviso por destinatario.
- **Cola `NotificacionStaff`** (durable, idempotente por dedup_key). Django ENCOLA; vos DRENÁS.
- Texto del aviso ya armado, ej.:
  `🔔 *Nueva tarea · Operación*` / `Preparar servicio – Tina Llaima (Reserva #123)` / `📌 Reserva #123` / `Responde "ok" cuando la tengas controlada.`

## Lo que falta — aremko-cli (tu lado): el canal saliente proactivo
1. **Poll** `GET /api/staff/notificaciones?limit=50` (header `X-API-Key: <LUNA_API_KEY>`) cada N seg
   (o piggyback en tu polling actual). Devuelve `{count, notificaciones:[{id, telefono, texto, dedup_key, origen, creada}]}`.
2. Por cada una → **enviar `texto` por WhatsApp** al `telefono` (path de /whatsapp/reply, igual que el briefing).
3. **Marcar**: `POST /api/staff/notificaciones/marcar` body `{"ids":[...], "estado":"enviada"}` (o
   `"fallida"` + `"error"` opcional). Idempotencia: ya marcada → no se reenvía.

## ⚠️ Ventana de 24h (importante)
Esto es PROACTIVO (push), no reactivo. Durante el turno Jorge interactúa seguido → la ventana suele
estar abierta y el free-form funciona. Si está cerrada, el free-form falla (#131047 o similar) →
marcá `fallida` con el error; en una v2 evaluamos plantilla utility para garantizar entrega fuera de
ventana. Para arrancar (Jorge en turno activo), free-form alcanza.

## E2E para probar
Jorge activa `recibe_avisos_operacion` en su número → se hace check-in de una reserva con tina →
control_gestion crea la tarea → Django encola → vos drenás y enviás → a Jorge le llega el aviso al
celular. (Para probar sin reserva real: crear una Task de swimlane OPS/RX en el admin de control_gestion.)

## Después (no en este handoff)
- Recordatorio de cumplimiento: cuando `promise_due_at` pasa y la tarea sigue pendiente → aviso
  (reusa el cron `preparacion-servicios`). Lo armo del lado Django y lo encolo igual.
- Vista on-demand: Jorge pregunta "qué tengo / estado del spa" → Luna responde su `mi-día`.
