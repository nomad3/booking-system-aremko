# BRIEF H-072 · M17 Creación de Historias — Fase 1: Manual + Puente + Registro de uso

> **Para:** agente Django (`~/dev/booking-system-aremko`).
> **Continúa:** H-071 (explorador B1 + ingesta B1.5 + componer B2-A, todo LIVE en prod).
> **Es la Fase 1** del roadmap de 6 fases de "Creación de Historias" del M17, aprobado por
> Jorge 2026-07-25. Plan producto: `datamatic-hospitality/docs/PLAN_M17_PRODUCCION_PIEZAS.md`.
> **Responde tu pregunta abierta de B2-B** (cómo enganchar la historia a la publicación).

## Objetivo Fase 1
Cerrar el ciclo **brief → historia → publicación** en modo **MANUAL**, y sembrar el cimiento
del **anti-repetición** (registro de uso), todo en Django server-rendered.

Flujo de Angélica: desde **"Publicaciones de hoy"** → elige una publicación → **"Crear
historia"** → elige foto del catálogo → el **texto del brief (`copy_json`) ya viene
precargado** en el composer → ajusta con los controles (ya existen en B2-A) → **aprueba** →
la historia queda **enganchada** a la `PublicacionPlanificada` + se **registra el uso** de la foto.

## Contexto del modelo (ya existe, reusar)
`PublicacionPlanificada` (marketing_briefs) ya tiene: `copy_json` (el texto), `estado`,
`material_urls` + `material_meta` (JSON), **`segmentos`** (carrusel: cada item con
`{indice, titulo, texto, material_urls, material_meta, ...}`), `dia/canal/tipo`. El endpoint
API `publicacion_material` (subidas de archivo de aremko-cli) **queda intacto** — esta Fase
usa el **camino interno Django (ORM)**.

## 1. Pantalla "Publicaciones" (Django, staff)
- Vista server-rendered, **misma estética boutique** del explorador. Ruta sugerida
  `/marketing/publicaciones/` (el agente elige el namespace/app; usa datos de
  `marketing_briefs` + el composer de `catalogo_clips`).
- Lista las `PublicacionPlanificada` (por día / semana en curso) como **tarjetas**: `dia`,
  `canal/tipo`, el copy (de `copy_json`), `estado`, y **preview del material** si ya tiene.
- Botón por tarjeta: **"✍️ Crear historia"** → abre el composer con el contexto de esa publicación.
- Botones **"🤖 Automática"** y **"⚡ Generar las de hoy"** **visibles pero DESHABILITADOS**
  (ganchos de Fase 2/3, "Pronto…").

## 2. Puente publicación → composer (texto precargado)
- Al abrir el composer desde una publicación, **precargar el texto desde `copy_json`** (el
  copy de esa historia). Angélica no reescribe; puede editarlo.
- El composer ya existe (B2-A); solo recibe **texto inicial + `pub_id`** (y `segmento` si
  aplica — para el carrusel de Fase 4; en Fase 1 opera pieza de 1 imagen).

## 3. Enganchar la historia a la publicación — **responde B2-B**
- La historia compuesta es una **`cloud_url`** (transformación Cloudinary; **ya está en la
  nube**). **NO re-subir.** Guardar por **ORM directo** (mismo proyecto): agregar la URL a
  `PublicacionPlanificada.material_urls` (o al **segmento** correspondiente si fuera carrusel)
  + su meta a `material_meta`.
- **Guardar la receta** de la historia (`{texto, posicion, preset, clip_id, tipo:'historia'}`)
  junto al item de material (p.ej. en `material_meta[i]`) para poder **RE-EDITAR** después.
  El shape exacto lo decides tú.
- Actualizar el `estado` de la publicación al enganchar (p.ej. → `con_material`/`listo`).
- **No** se necesita `material_desde_url`: el endpoint API queda para las subidas de archivo
  de aremko-cli; el flujo interno Django va por ORM.

## 4. Registro de uso del clip (cimiento anti-repetición de Fase 2)
- Al aprobar/enganchar, **registrar el uso del clip**: modelo nuevo
  **`UsoClip(clip FK, fecha, publicacion FK nullable, canal)`** en `catalogo_clips`
  (migración **drift-safe**, app aislada) + **desnormalizar `Clip.ultimo_uso` (Date)** para
  el query rápido del auto-pick.
- No cambia la UI; es el dato que la **Fase 2 (auto-pick)** usará para **no repetir fotos**.
  Sembrarlo desde ya = cuando llegue el auto-pick, hay historial.

## 5. Diseño (transversal M17 — "que se vea bonito")
- **Preview fiel (WYSIWYG):** es el JPG final de Cloudinary → lo que ve = lo que descarga.
- **Fluido:** cambiar la receta = nueva URL = preview al instante (sin recargas pesadas).
- Estética boutique consistente con el explorador — el preview de la historia es la **cara
  del M17**, tiene que verse bien.

## Fuera de alcance Fase 1 (ganchos dejados)
- Auto-pick (Fase 2), batch (Fase 3), carrusel multi-slide en la UI (Fase 4 — el modelo ya
  soporta `segmentos`; Fase 1 opera 1 imagen), chat de ajuste conversacional (Fase 5),
  video (Fase 6). Video y multi-tenant real: mantener port-friendly.

## Checklist de cierre
- [ ] Pantalla `/marketing/publicaciones/` (staff) con tarjetas + estado + botón "Crear historia".
- [ ] Composer recibe `copy_json` precargado + `pub_id`.
- [ ] Enganche por ORM: `material_urls` + receta + `clip_id`; `estado` actualizado.
- [ ] `UsoClip` + `Clip.ultimo_uso` (migración drift-safe) + registro al aprobar.
- [ ] Botones auto/batch visibles pero deshabilitados (ganchos Fase 2/3).
- [ ] `check` + prueba en prod: crear una historia manual desde una publicación real →
      queda enganchada + uso registrado + preview correcto.
