# RESPUESTA H-012 — Bandeja de envíos por plantilla (mecanismo de aprobación)

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-14 · **Responde a:** `BRIEF_H-012_bandeja_plantillas_automatica.md`
> **Estado:** 🟢 Mecanismo IMPLEMENTADO (Django). Falta: mapeo de plantillas (Jorge) + tu UI.

## Buena noticia: casi todo ya existía

El cron diario (`generar_bandeja_whatsapp_diaria`) ya segmenta por motivos P0–P6
(reactivación 95-105d, momentos clave día 30/60/80, mesa chica, dormidos…), `ScriptWhatsApp`
ya tiene `meta_template_name`/`meta_variables_orden`, y el pipeline `pending-template-sends`
→ `run-template-campaign` → `mark-template-sent` ya funciona. **No reinventamos nada.**

## Lo que agregué: gate de aprobación (modo aprobación primero)

Nuevo flujo de estados de `ContactoWhatsApp`:
`pendiente` (= por aprobar, lo deja el cron) → **`aprobado`** (Deborah aprobó) → `enviado`.

- `pending-template-sends` ahora devuelve **`estado='aprobado'`** (antes `'pendiente'`) → **nada
  se envía hasta que se apruebe**. El cron no cambió (sigue dejando `pendiente`).
- `'aprobado'` es solo un valor de string en el `estado` (CharField) → **sin migración**.

## Contratos (tu lado)

Todos luna-key.
- `GET /api/whatsapp/bandeja-envios?estado=por_aprobar` →
  `{ok, count, envios:[{contacto_id, cliente_id, cliente_nombre, phone, motivo, script_id,
  plantilla, preview, salva, prioridad, fecha_sugerido}]}`. Solo lista contactos `pendiente`
  cuyo script YA tiene plantilla Meta (los que se pueden enviar). `preview` = texto renderizado.
- `POST /api/whatsapp/bandeja-envios/<id>/aprobar` → `{ok, contacto_id, estado}`.
- `POST /api/whatsapp/bandeja-envios/<id>/descartar` → `{ok, contacto_id, estado}`.
- `POST /api/whatsapp/bandeja-envios/aprobar-lote` body `{ids:[...]}` o `{motivo:"<eje_valor>"}`
  → `{ok, aprobados:N}`.
- **Enviar aprobados:** dispara tu `run-template-campaign` (Go) → llama `pending-template-sends`
  (ahora solo trae `aprobado`) → envía por Cloud API → `mark-template-sent` (pasa a `enviado`).

**Tu UI:** "Envíos de plantilla por aprobar": lista por motivo con cliente + plantilla + preview,
Aprobar/Descartar (individual + lote) + "Enviar aprobados". Proxies a los 4 endpoints.

## Lo que falta del lado de Jorge: mapeo motivo→plantilla

Hoy NINGÚN script tiene `meta_template_name`. Hasta que se mapee, la bandeja de envíos sale
vacía (no hay plantilla con la cual enviar). Jorge mapea en el admin de `ScriptWhatsApp`
(campos `meta_template_name` + `meta_variables_orden`), guiado por el comando
`python manage.py scripts_para_mapeo` que lista los scripts **de simple a complejo** con su
cuerpo actual y variables, para calzar cada `vac_*` aprobada con el contenido que ya se enviaba.

Orden sugerido (lo define el comando): salva 1 + genéricos primero (Dormido, En Prueba,
Leal/Campeón), luego los segmentados (En Riesgo por estilo/contexto) y al final Refugio.

## Pendiente para activar
- Deploy (pusheado). Sin migración.
- Jorge mapea las primeras plantillas (las más simples) en el admin.
- Tu UI + "Enviar aprobados".
- Modo automático con tope diario → iteración futura (cuando la calidad/tier se mantenga sana).
