# BRIEF H-073 · M17 Creación de Historias — Fase 2: Auto-pick (foto automática determinista)

> **Para:** agente Django (`~/dev/booking-system-aremko`).
> **Continúa:** H-072 (Fase 1: pantalla de publicaciones + puente + `UsoClip`/`Clip.ultimo_uso`, LIVE).
> **Es la Fase 2 de 6** del roadmap de "Creación de Historias" del M17.
> **Diseño acordado** (Django + coordinador, 2026-07-25): **el brief emite el CRITERIO de foto;
> el auto-pick es 100% determinista.** Plan: `datamatic-hospitality/docs/PLAN_M17_PRODUCCION_PIEZAS.md` §11.

## Objetivo
Activar el botón **"🤖 Generar"** de cada historia en `/marketing/publicaciones/`: el sistema
**elige la foto solo** (sin LLM en la selección) y compone la historia con el texto del brief.

## Principio (regla de oro)
El LLM ya participó **una vez**, al escribir el brief — ahí también deja anotado **qué foto va**.
La **selección final de la foto es 100% código** (filtro + orden), auditable, sin adivinanzas.
Es lo correcto porque el modo automático publica **sin revisión humana**.

## Parte A — El brief emite `criterio_foto` (marketing_briefs)
- Actualizar el **generador del brief** (el prompt del LLM que produce el JSON de cada pieza —
  ubícalo tú; mismo patrón que `prompt_imagen_ia` de H-064) para que **cada historia/segmento**
  incluya un `criterio_foto` con los **enums de `catalogo_clips.Clip`**:
  ```json
  "criterio_foto": {
    "area": "tina", "nombre_comercial": "",
    "vapor_preferido": true, "decoracion": "sin", "momento": "indistinto"
  }
  ```
  - `nombre_comercial: ""` = cualquiera de esa área sirve.
  - `momento: "indistinto"` / `decoracion: ""` = no filtra por ese campo.
  - `vapor_preferido: true` → `vapor ∈ {sí, sí (IA)}`; `false` → sin exigir vapor.
- `_segmentos_de_historias` (services.py) **guarda `criterio_foto` en cada segmento**. Para
  piezas de 1 sola imagen (sin segmentos): guardarlo a nivel pieza (en `copy_json`).
- **Secuencia esperada:** el `criterio_foto` aparece en los briefs **generados desde este
  cambio** (el próximo). Los briefs YA existentes no lo tienen → ver fallback.
- **Fallback (historia sin `criterio_foto`):** NO adivinar con LLM. Si se puede derivar un
  default suave por `canal/tipo` (p.ej. story → `area` más común), usarlo con aviso; si no,
  **deshabilitar "🤖 Generar" en esa historia** y dejar solo **"✍️ Manual"** (Fase 1).

## Parte B — Auto-pick determinista (catalogo_clips)
`seleccionar_clip(criterio, dias=60, permitir_personas=False)` → devuelve `(clip, nivel, aviso)`:
- Query base:
  `Clip.objects.filter(area=criterio.area [, nombre_comercial__icontains si no vacío]
  [, vapor__in=['sí','sí (IA)'] si vapor_preferido] [, decoracion=… si no vacío]
  [, momento=… si != indistinto], personas=False, estado='ok')
  .exclude(ultimo_uso__gte=hoy-dias).order_by('-keeper','ultimo_uso')` → primera.
- **Degradación en cascada** (devuelve el `nivel` usado para ser transparente en la UI):
  1. criterio completo · keeper · sin personas · fresca (60 d)
  2. sin exigir keeper
  3. relajar `momento`/`decoracion`
  4. permitir **repetir** (la de `ultimo_uso` más antiguo) → aviso *"foto repetida"*
  5. permitir **personas** → aviso *"tiene personas, revísala antes de publicar"*
  6. nada → *"no hay foto para este criterio; elige manual o sube fotos de esta área"*
- Filtros **duros** salvo degradación: `personas=False` y no-repetir (60 d) se relajan **solo**
  en los niveles 4-5, siempre con aviso.

## UI (sobre la pantalla de Fase 1)
- **Activar** el botón **"🤖 Generar"** (hoy deshabilitado) por historia → llama `seleccionar_clip`
  con su `criterio_foto` → **compone** (reusa el composer B2-A con el texto de la historia +
  preset boutique por defecto) → muestra **preview** + **qué foto y criterio se usaron** + el
  **aviso** si hubo degradación.
- Acciones sobre el preview: **✓ Aprobar/Enganchar** (reusa Fase 1 → registra `UsoClip`),
  **🔄 Otra foto** (siguiente candidata: mismo query, saltando la ya mostrada),
  **✍️ Manual** (explorador de Fase 1).
- **"⚡ Generar las de hoy"** sigue **DESHABILITADO** (es Fase 3).

## Fuera de alcance Fase 2
- Batch "las de hoy" (F3), carrusel (F4 — el modelo ya tiene `segmentos`), chat de ajuste
  (F5), video (F6). Multi-tenant real: mantener port-friendly.

## Checklist de cierre
- [ ] Brief emite `criterio_foto` por historia (+ segmentos; pieza de 1 imagen en `copy_json`)
      + fallback para historias sin criterio.
- [ ] `seleccionar_clip` determinista con **degradación en cascada** + `nivel`/`aviso` auditables.
- [ ] Botón "🤖 Generar" activo → auto-pick → compone → preview con foto/criterio/aviso.
- [ ] Acciones: Aprobar (registra `UsoClip`), 🔄 Otra foto, ✍️ Manual.
- [ ] Prioriza **sin personas** + **no-repetir 60 d** (duros salvo degradación con aviso).
- [ ] `check` + prueba en prod: una historia con `criterio_foto` → "🤖 Generar" → foto
      correcta (del área/criterio), sin personas, no repetida; y una historia sin criterio →
      botón deshabilitado con "usa Manual".
