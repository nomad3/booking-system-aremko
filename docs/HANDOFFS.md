# HANDOFFS — Bitácora de encargos entre agentes (Django ↔ aremko-cli)

> Fuente de verdad del trabajo cruzado entre el **agente Django**
> (`~/dev/booking-system-aremko`) y el **agente aremko-cli**
> (`~/Documents/GitHub/aremko-cli.nosync`). Si se corta la sesión/energía,
> este archivo + `git log` reconstruyen en qué quedamos.

## Tabla de handoffs

| ID | Qué | Implementa | Estado | Última actualización |
|----|-----|-----------|--------|----------------------|
| H-001 | Antiduplicado 48 h + orden gracias→resumen + cron normalizar ciudades (bandeja Conexión-Masajes) | Django → luego aremko-cli (UI) | ✅ CERRADO — Django `a10d1c9` + UI aremko-cli `2f0f793` + cron-job.org diario 07:30. Validado por Jorge en prod 2026-06-10 (bandeja OK; sin casos de bloqueo activos aún — los escenarios de candado/forzar se comprobarán con el uso). Contrato: `RESPUESTA_ANTIDUPLICADO_MASAJES.md` | 2026-06-10 (agente Django) |
| H-002 | Auditar discrepancia leads Refugio (Pixel 14 vs BD 3) + endpoint `GET /api/refugio-leads/` que LISTE leads (no solo conteos) para CPL real + cierre Etapa 4b (cruce teléfono→reservas→ROAS) | Django + aremko-cli | 🔵 INTEGRADO — Django `9f6f078` + aremko-cli `5a9676c` (GetRefugioLeads + applyRefugioSalesAndROAS cruza teléfono form/WhatsApp → reservas; card muestra ingresos/ROAS + CPL formulario vs intención). Pendiente: deploy Render/Vercel + validación de Jorge en prod. Diagnóstico 14vs3 en RESPUESTA_H-002 | 2026-06-11 (agente aremko-cli) |
| H-003 | `GET /api/masaje/outbox/` tarda >10s → timeout en Conexión-Masajes (aremko-cli). Optimizar la vista (sospecha: `_serialize(include_preview=True)` renderiza N previews inline, o falta índice en `SeguimientoBienestarMasaje(estado, fecha_programada)`) | Django | ✅ CERRADO — Django `47d141c` (N+1 eliminado en `outbox_list`, ~1200→~12 queries, sin preview inline). Jorge confirmó bandeja OK en prod 2026-06-13. **aremko-cli verificó el contrato:** NO se consume `preview_html` inline (solo era campo opcional en `types.ts`, nunca leído); el modal "Ver" usa `<iframe src={previewUrl(id)}>` (`page.tsx:714`) → endpoint `/preview/<id>/` (text/html, sin cambios) → no le afecta. Ver `RESPUESTA_H-003` | 2026-06-13 (agente aremko-cli) |
| H-004 | Editar `Cliente.nombre` desde la bandeja de WhatsApp (los nombres auto-creados no coinciden con el real). Endpoint `POST /api/whatsapp/conversations/<phone>/editar-nombre/` (luna-key, body `{nombre}`, audita MovimientoCliente) | Django (endpoint) + aremko-cli (proxy Go + UI lápiz) | 🔵 INTEGRADO (Django `37c92ef` + aremko-cli `5e88ffd`) — `POST /api/whatsapp/conversations/<phone>/editar-nombre/` (luna-key, body `{nombre}`) en prod, sin cambios al contrato. Valida no-vacío, audita MovimientoCliente, devuelve `{ok, cliente_id, cliente_nombre}`. Confirmado: relleno auto sigue `if nombre and not cliente.nombre` (no pisa la corrección). aremko-cli desplegó proxy Go + lápiz inline en el encabezado de la conversación (endpoint proxy verificado en prod). Pendiente validación de Jorge → CERRADO. Ver `RESPUESTA_H-004` | 2026-06-13 (agente aremko-cli) |
| H-005 | "Marcar como leído": que el badge "1" y el filtro "solo pendientes" se basen en `requiere_atencion` (que responder/marcar-atendido ya limpian) y no en timestamp (`last_in > last_out`), para poder cerrar una conversación sin respuesta. + botón ✓ en aremko-cli | Django (lógica lista) + aremko-cli (botón) | 🟡 SOLICITADO — diagnóstico/contrato en `BRIEF_H-005_marcar_leido_pendiente.md`. Cambio chico en `conversations` (badge=`req`, `_pendiente`=`req>0`). aremko-cli agrega botón que llama al `marcar-atendido` existente, lo despliega tras el cambio. Opcional: no marcar `requiere_atencion` para `type='reaction'` | 2026-06-13 (agente aremko-cli) |

## Estados

`SOLICITADO` → `EN PROGRESO (lado X)` → `IMPLEMENTADO (esperando al otro lado)` → `INTEGRADO` → `CERRADO`

- **SOLICITADO**: existe el `BRIEF_H-xxx_*.md`, nadie lo tomó aún.
- **EN PROGRESO (lado X)**: el agente X está trabajando. ⚠️ Marcar ANTES de empezar.
- **IMPLEMENTADO**: un lado terminó y publicó su `RESPUESTA_H-xxx_*.md`; falta el otro.
- **INTEGRADO**: ambos lados desplegados, falta validación de Jorge en producción.
- **CERRADO**: validado funcionando.

## Reglas del protocolo (para ambos agentes)

1. **Un ID por encargo cruzado**: serie `H-001`, `H-002`, … (los AR-### siguen
   siendo para bugs/issues internos del booking system). Los documentos llevan
   el ID: `docs/BRIEF_H-002_<tema>.md` y `docs/RESPUESTA_H-002_<tema>.md`.
2. **Commit + push del cambio de estado ANTES de empezar a trabajar** (fila →
   `EN PROGRESO (Django)` o `EN PROGRESO (aremko-cli)`), y de nuevo al terminar.
   El estado vive en git, no en la memoria de la sesión.
3. **Este archivo vive solo en el repo Django** (aquí ya viven los briefs).
   El agente aremko-cli lo lee y edita directamente en
   `~/dev/booking-system-aremko/docs/HANDOFFS.md` y commitea SOLO este archivo
   (y briefs/respuestas) en este repo — nunca código del otro lado.
4. **Tras un corte** (energía, sesión, contexto): leer esta tabla; si hay un
   `EN PROGRESO`, revisar `git log --oneline -10` y `git status` del repo que
   implementa para ver qué alcanzó a commitearse. No re-implementar sin
   verificar primero.
5. **Mensajes de commit de la bitácora**: `docs(handoffs): H-xxx → <estado>`.
6. **Histórico previo al protocolo** (referencia): brief de la bandeja masajes
   (`BRIEF_BANDEJA_MASAJES_AREMKO_CLI.md`), respuesta geo
   (`RESPUESTA_OUTBOX_GEO_AREMKO_CLI.md`) — anteriores a la numeración, no se renombran.
