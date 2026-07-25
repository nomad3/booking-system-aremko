# BRIEF H-070 · Catálogo de Clips (M17) — Fase A: modelo + ingesta + etiquetado IA

> **Para:** agente Django (`~/dev/booking-system-aremko`).
> **Origen:** validado local para Aremko esta semana (catálogo de 282-291 clips en
> `AREMKO/catalogo.json` + skills `/catalogar`, `/post-aremko`, `/historia-aremko`).
> Ahora se lleva a **producción** como base del **M17 (Asistente de Publicaciones)**.
> Repo destino: **Aremko primero** (cliente cero); diseñar port-friendly a DH multi-tenant.
> Plan producto: `datamatic-hospitality/docs/PLAN_M17_PRODUCCION_PIEZAS.md`.
> **Alcance de este handoff: solo Fase A** (el cimiento servidor). NO incluye el render en
> navegador (front, otro handoff) ni video (se procesa local por ahora).

## Objetivo
Que el catálogo de fotos deje de vivir en un JSON local y viva en Django, y que se puedan
**agregar fotos nuevas con taxonomía asistida por IA**: subir foto → la IA propone la
taxonomía → el operador confirma/corrige → queda disponible para la automatización de
publicaciones.

## Arquitectura (contexto, no discutir aquí)
Separamos **cerebro (servidor)** de **píxeles (navegador)**. Este handoff es 100% servidor:
- La **visión** solo se usa **al catalogar** (aquí), no al componer.
- Los **masters pesados quedan locales**; a Cloudinary sube solo la **imagen optimizada**
  (~1440px máx, `q_auto,f_auto`) + la metadata a la tabla. (Cloudinary Aremko va al 40% de
  60 créditos ~US$29/mes; el catálogo interno suma marginal — mantener las imágenes chicas.)

## 1. App nueva `catalogo_clips` (aislada, drift-safe)
Crear app aislada (patrón `whatsapp_agent`/`personal_operativo`): migración `0001_initial`
sin dependencias cruzadas, para no tocar el drift AR-033/AR-034 (ver
`feedback_makemigrations_drift_safe`).

### Modelo `Clip`
Campos universales (queryables, explícitos):
- `archivo` (Char) — nombre original, referencia.
- `imagen` — la imagen optimizada en Cloudinary (usar el storage de imágenes que ya usan;
  subir con transformación `q_auto,f_auto,c_limit,w_1440`). Guardar también `cloud_url`.
- `tipo` (Char: `foto`/`video`) — Fase A opera `foto`; dejar el campo (video llega después).
- `area` (Char: `tina|masaje|cabaña|entorno|detalle|aereo|recepcion|entorno_region`).
- `nombre_comercial` (Char, blank) — nombre de tina/cabaña (ver taxonomía §3).
- `momento` (Char: `dia|atardecer|noche|indistinto`), `estacion` (`invierno|verano|indistinto`).
- `vapor` (Char: `no|sí|sí (IA)`), `decoracion` (Char: `con|sin|""`).
- `personas` (Bool), `permiso` (Char: `libre|revisar_derechos`).
- `calidad` (Char: `alta|media`), `keeper` (Bool).
- `descripcion` (Char), `orientacion` (Char, blank), `estado` (Char: `ok|revisar|descartado`),
  `fuente` (Char: `disco|chatgpt|...`), `nota` (Text, blank), `origen` (Char, blank — variantes).
- `etiquetas` (JSONField, lista), `apto_para` (JSONField, lista).
- `atributos` (JSONField, default dict) — **extras por vertical** (spa≠restaurante); en Aremko
  guarda p.ej. `hidromasaje`. Los universales van explícitos; lo específico del rubro, aquí.
- `creado`/`actualizado` (auto).
- **Port multi-tenant:** dejar comentado/preparado un FK `empresa` (nullable) para cuando
  migre a DH; en Aremko es mono-tenant (no crear el FK aún, solo dejar el hueco documentado).

Admin (`@admin.register`): superuser, list_display con area/nombre/keeper/vapor/estado +
list_filter + search — para **curación humana** (patrón "IA propone, humano cura").

## 2. Servicio de etiquetado IA `catalogo_clips/tagging.py`
Reusar el núcleo de visión existente: `marketing_briefs/revision_service._chat_vision`
(OpenRouter + `MARKETING_REVISION_LLM_MODEL`). Nuevo `TAGGING_SYSTEM_PROMPT` que, dada la
imagen, **proponga** todos los campos según la taxonomía §3. Devuelve JSON con el borrador.
No inventar: si duda del área o nombre, dejar `nombre_comercial=""` y `estado="revisar"`.

## 3. Taxonomía Aremko (para el prompt de etiquetado) — LITERAL
- **Tinas — nombre por FORMA + hidromasaje:** redonda + hidromasaje → **Villarrica-Llaima** ·
  octagonal (8 lados) sin hidromasaje → **Tronador-Calbuco** · rectangular sin hidromasaje →
  **Osorno-Hornopirén** · rectangular con hidromasaje → **Puyehue-Puntiagudo** · rectangular
  interior azul (agua fría) → **Yates**. (Gemelas idénticas → nombre-par; Jorge da el
  individual: Hornopirén/Tronador/Puntiagudo, etc.)
- **Cabañas — 5:** **Torre** (única redonda y de 2 pisos, domo) · **Laurel** (moderna de
  vidrio/palafito) · **Acantilado** · **Tepa** · **Arrayán** (1 piso; las 4 de un piso son
  difíciles de distinguir por foto → proponer `nombre_comercial=""` y que el humano nombre).
- **Otros espacios:** el domo de masajes se llama **"Sala Sol"**; hay **Recepción Aremko** y
  **Recepción domos masajes**; **pasarelas** (+300 m) → etiqueta `pasarela` bajo `entorno`.
- **`decoracion`:** ambientación (velas/vino/flores/bandeja) = SERVICIO ADICIONAL → `con`;
  base → `sin`.
- **`vapor`:** solo tinas calientes con agua; NUNCA en la Yates (fría) ni tinas vacías.
- **`personas`:** clientes reconocibles → `personas=true` + `permiso="revisar_derechos"`
  (Deisy y su pareja = autorizado; masajes "a jorge" = él mismo).
- **`keeper`:** true si es hero (sin personas, nítida, distinta, no duplicado).
- **Guarda de marca:** SOLO material real; nada sintético entra al catálogo real.

## 4. API (auth `X-API-KEY == AUTOMATION_API_KEY`, patrón de `marketing_briefs/api_views`)
- `POST /marketing/api/catalogo/ingesta/` — multipart imagen → sube optimizada a Cloudinary →
  corre etiquetado → devuelve `{cloud_url, draft:{area,nombre_comercial,momento,vapor,...}}`
  (borrador, **sin** persistir aún).
- `POST /marketing/api/catalogo/` — guarda el registro confirmado (taxonomía ya ajustada por
  el operador) → crea `Clip`. Devuelve el objeto.
- `GET /marketing/api/catalogo/` — lista con filtros: `area, nombre_comercial, keeper, vapor,
  momento, apto_para, estado, q(texto)` → para que el front la explore.
- `PATCH /marketing/api/catalogo/<id>/` — editar taxonomía / `estado` / `keeper`.

## 5. Semilla de los 282-291 registros actuales
Los datos están en `AREMKO/catalogo.json` (local) y las **fotos en el disco local** → la
carga inicial es un **push local→nube** (script LOCAL, lo entrega el lado aremko-cli/Jorge,
NO este agente): por cada keeper, sube la imagen optimizada + postea la metadata al endpoint
de guardar. **Django solo debe dejar los endpoints listos y idempotentes** (si llega un
`archivo` ya existente, upsert por `archivo`, no duplicar). Empezar por los **keepers** (~89)
para mantener Cloudinary liviano; el resto después.

## 6. Contrato para aremko-cli (front — otro handoff)
Documentar en `docs/CONTRATO_H-070_CATALOGO.md`: shapes exactos de request/response de los 4
endpoints (para construir después la **pantalla de ingesta con botones** y el explorador de
catálogo). El front y el **render en navegador** son handoff aparte (Fase B).

## 7. Fuera de alcance (explícito)
- Render/composición de la pieza (Fase B; el render de imagen va en el **navegador**).
- **Video** (se procesa **local** por ahora; server a definir — ver PLAN_M17_PRODUCCION_PIEZAS §5.5).
- Multi-tenant real (Aremko mono-tenant; solo dejar el modelo port-friendly).
- Auto-pick (matchear brief→foto) y "receta de render" → Fase B.

## Checklist de cierre
- [ ] App `catalogo_clips` + modelo `Clip` + admin + migración 0001 drift-safe.
- [ ] `tagging.py` (reusa `_chat_vision`) + `TAGGING_SYSTEM_PROMPT` con la taxonomía §3.
- [ ] 4 endpoints con `X-API-KEY`, ingesta idempotente (upsert por `archivo`).
- [ ] Cloudinary optimizado (`q_auto,f_auto,w_1440`), master NO se sube.
- [ ] `docs/CONTRATO_H-070_CATALOGO.md` con los shapes.
- [ ] Tests + `check`. Deploy + migrate desde Shell (auto-migrations off).
- [ ] Verificar en prod con 1 foto real (ingesta → draft → guardar → aparece en `GET`).
