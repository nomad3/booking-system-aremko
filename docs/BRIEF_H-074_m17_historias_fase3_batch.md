# BRIEF H-074 · M17 Creación de Historias — Fase 3: Batch "Generar las de hoy"

> **Para:** agente Django (`~/dev/booking-system-aremko`).
> **Continúa:** H-073 (Fase 2 auto-pick determinista, LIVE y validado e2e).
> **Es la Fase 3 de 6** del roadmap de "Creación de Historias" del M17.
> **Reusa todo lo que ya existe:** `seleccionar_clip` (ya acepta `excluir_ids`), el composer
> B2-A y el enganche de Fase 1 (`material_urls`+receta+`UsoClip`).

## Objetivo
Activar **"⚡ Generar las de hoy"** (hoy deshabilitado): genera **en lote** todas las historias
auto-generables de un día, de una sola vez, **sin repetir foto entre ellas** ni con el histórico.

## 1. Alcance del botón
- Activar **"⚡ Generar las de hoy"** → genera las historias del **día** que sean
  **auto-generables** = tienen `criterio_foto` **y** aún no tienen material enganchado
  (respeta lo ya hecho, p.ej. la #31).
- Sugerencia UX (tú eliges lo natural): un botón **"⚡ Generar" por cada grupo de día** +/o el
  global "las de hoy" (día actual). Lo importante es que opere **por día** (3–4 historias).

## 2. Anti-repetición dentro del lote (lo clave)
- Iterar las historias auto-generables del día **acumulando los `clip_id` ya elegidos** en un
  set y pasándolo a `seleccionar_clip(criterio, excluir_ids=usados)` en cada iteración → **ninguna
  repite foto** con otra del mismo lote (el histórico de 60 d ya lo excluye la función).
- **Diversidad de tina (deseable, no obligatorio):** si varias historias comparten un criterio
  genérico (`area=tina`, `nombre_comercial=""`), intentar **no repetir `nombre_comercial`** dentro
  del lote mientras haya stock (para que no salgan 3 fotos de la misma tina), degradando si se agota.

## 3. Flujo
- "⚡ Generar las de hoy" → por cada historia auto-generable: `seleccionar_clip` (con `excluir_ids`
  acumulado) → **compone** (B2-A con el texto de la historia) → **engancha** (queda `estado='lista'`
  con miniatura + receta + registra `UsoClip`, igual que Fase 1).
- Al terminar → **resumen** claro: *"Generé N historias · M con aviso de degradación · K
  quedaron para Manual (sin criterio)"*.
- **"Lista" ≠ "publicada":** nada se sube a Instagram solo. Angélica **revisa las miniaturas** en
  la lista y ajusta las que quiera (**🔄 Otra foto** / **✍️ Manual** / editar texto). Re-generar
  una historia **REEMPLAZA** su material (no acumula un segundo).

## 4. Reusa (no reinventar)
- `catalogo_clips.seleccionar_clip(..., excluir_ids=...)` — la firma ya lo contempla.
- El composer B2-A y el enganche por ORM de Fase 1 (`material_urls`/`material_meta`/receta/`UsoClip`).

## Fuera de alcance Fase 3
- Carrusel (F4 — el modelo ya tiene `segmentos`), chat de ajuste (F5), video (F6).
- Historias **sin** `criterio_foto` (video/audio/reseña/quiz/personas) **NO entran al batch** →
  quedan solo en Manual (mismo fallback de Fase 2).

## Checklist de cierre
- [ ] "⚡ Generar las de hoy" activo → batch de las auto-generables del día (con criterio, sin material).
- [ ] Anti-repetición en el lote vía `excluir_ids` acumulado (+ diversidad de `nombre_comercial` si se puede).
- [ ] Cada historia: `seleccionar_clip` → compone → engancha (`lista` + `UsoClip`).
- [ ] **Resumen** al terminar (generadas / con aviso / para manual).
- [ ] Re-generar una historia **reemplaza** su material (no acumula).
- [ ] Respeta lo ya enganchado (no re-genera historias con material, p.ej. la #31).
- [ ] `check` + prueba en prod: un día con varias auto-generables → "⚡" → todas quedan listas
      con fotos **distintas** entre sí + resumen correcto.
