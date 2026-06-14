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
| H-004 | Editar `Cliente.nombre` desde la bandeja de WhatsApp (los nombres auto-creados no coinciden con el real). Endpoint `POST /api/whatsapp/conversations/<phone>/editar-nombre/` (luna-key, body `{nombre}`, audita MovimientoCliente) | Django (endpoint) + aremko-cli (proxy Go + UI lápiz) | ✅ CERRADO — Django `37c92ef` + aremko-cli `5e88ffd`. `POST /api/whatsapp/conversations/<phone>/editar-nombre/` (luna-key, body `{nombre}`); valida no-vacío, audita MovimientoCliente, devuelve `{ok, cliente_id, cliente_nombre}`. Relleno auto sigue `if nombre and not cliente.nombre` (no pisa la corrección). aremko-cli: proxy Go + lápiz inline en el encabezado. **Jorge validó en prod 2026-06-13: "funcionando impecable".** Ver `RESPUESTA_H-004` | 2026-06-13 (agente aremko-cli) |
| H-005 | "Marcar como leído": que el badge "1" y el filtro "solo pendientes" se basen en `requiere_atencion` (que responder/marcar-atendido ya limpian) y no en timestamp (`last_in > last_out`), para poder cerrar una conversación sin respuesta. + botón ✓ en aremko-cli | Django (lógica lista) + aremko-cli (botón) | ✅ CERRADO — Django `eac641a` + aremko-cli `1da3b6e`. `conversations`: `_pendiente`=`req>0` y badge `sin_responder`=`req` (basado en `requiere_atencion`, no timestamp); reacciones (`type='reaction'`) ya no marcan pendiente. aremko-cli: botón "✓ Leído" en el encabezado (llama al `marcar-atendido` existente + refresca). **Jorge validó en prod 2026-06-13: "H-005 ok".** Ver `RESPUESTA_H-005` | 2026-06-13 (agente aremko-cli) |
| H-006 | Ordenar la bandeja con **pendientes primero** (antes del corte `[:limit]`): un blast de plantillas salientes empuja las pendientes hacia abajo y el `agg[:limit]` puede hacer que una conversación sin responder ni se devuelva | Django (orden en `conversations`) | ✅ CERRADO — Django `76550e1`: `conversations` ordena `(req>0, ultimo_ts)` desc ANTES de `[:limit]`; las pendientes quedan arriba y no se caen por el corte aunque haya blast de salientes. aremko-cli: nada (respeta el orden). **Jorge validó en prod 2026-06-13: "orden ok, pendientes primero".** Ver `RESPUESTA_H-006` | 2026-06-13 (agente aremko-cli) |
| H-007 | **Agente IA que contesta WhatsApp** (plan por fases): responde SOLO sobre servicios publicados + productos con stock>0; grounding con catálogo vivo; modelo desde env Render, tono/on-off desde formulario aremko-cli; human-in-the-loop primero (F1 borrador → F2 auto-info → F3 auto+botón). Proyecto "Agentes IA Aremko" | Django (núcleo agente + grounding + config) + aremko-cli (UI control + borradores) | ✅ CERRADO (Fase 1) — app nueva aislada `whatsapp_agent` (drift-safe, migración `0001_initial` sin dependencias). Genera borrador con grounding de catálogo vivo (servicios `publicado_web`+`activo`, productos `publicado_web`+stock>0) vía patrón DPV/OpenRouter; config singleton (on/off, modo, tono, modelo, link reserva) editable desde admin + endpoint `GET/POST /api/whatsapp/agente/config`; `sugerencia_agente` colgado de `GET /api/whatsapp/conversation/?phone=` (generación lazy, no toca el inbound); escalamiento (heurística pre-LLM + `[ESCALAR]` del modelo), pausa por conversación, anti-injection, fallback seguro, sanitización ≤1000 chars. aremko-cli (`12a9b6b`→`cc02791`): página "Agente IA" (on/off, modo, tono, link, modelo) + proxy config; en la conversación precarga el cajón con el borrador ("✨ sugerido por IA") o muestra banner "Derivar a persona" si escala; **auto-genera el borrador al llegar un entrante nuevo** (sin tocar Actualizar); Actualizar regenera sin blanquear el hilo. **Jorge validó en prod 2026-06-13:** borradores con grounding real (masajes con precios; "¿venden comida?" → pizzas/tablas/café/jugos de productos con stock), auto-generación y escalamiento OK. Bugs resueltos en la validación: (1) el proxy Go no reenviaba `&sugerencia=1` [aremko-cli `57f74dc`]; (2) la pausa-por-conversación se aplicaba en modo borrador [Django `df56895`]. Contrato: modelo en el form (no env); sugerencia lazy opt-in (`&sugerencia=1`). **Iteración futura:** Fases 2 (auto-info) y 3 (auto+botón); refinar prompt con reglas de reserva por servicio (solo relajación/descontracturante se reservan online; el resto deriva a WhatsApp). Ver `RESPUESTA_H-007` | 2026-06-13 (agente aremko-cli) |
| H-008 | Botón **"Mensaje de ausencia"**: toggle manual que, al activarse, auto-responde a cada entrante una frase fija ("solo atendemos por www.aremko.cl…"); al desactivarse vuelve el flujo normal (Deborah/borrador agente) | Django (auto-respuesta en inbound + config `ausencia_activa`/`ausencia_mensaje`) + aremko-cli (toggle + editor) | 🟡 SOLICITADO — plan en `BRIEF_H-008_mensaje_ausencia.md`. Config reusa `agente/config`. Sugerido: anti-spam 1 vez por conversación cada N h + precedencia sobre el borrador. Quién envía (Django directo vs directiva→webhook Go aremko-cli): a criterio de Django, avisa y calzo. aremko-cli: sección "Mensaje de ausencia" en la página Agente IA | 2026-06-13 (agente aremko-cli) |

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
