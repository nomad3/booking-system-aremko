# DOSSIER DE TRASPASO · M17 (Asistente de Publicaciones) → Datamatic Hospitality

> **Autor:** agente Django (`booking-system-aremko`), quien construyó las 5 fases (H-070…H-074).
> **Para:** agente DH (`datamatic-hospitality`), sesión "DH".
> **Contexto:** `docs/MIGRACION_M17_A_DH.md` (el marco de producto/secuencia). Este documento es
> el **detalle técnico** que falta ahí — modelos exactos, contratos de datos, qué es portable
> tal cual vs. qué exige adaptación, y las trampas ya resueltas (para no re-descubrirlas).
> **Todo lo descrito acá está LIVE en prod (aremko.cl) desde 2026-07-24/25**, con tests y
> verificación real, no es un diseño en papel.

## 0. Qué es M17 en una frase

Un asistente que **redacta el copy semanal de redes con un LLM** y luego **elige la foto real
sola** (sin LLM, 100% código, auditable) para componer historias de Instagram listas para
revisar y publicar. La "regla de oro" que atraviesa todo el diseño:

> **El LLM participa UNA sola vez — al escribir el brief. La selección final de la foto es
> 100% código.** Nunca hay una segunda pasada de IA "adivinando" qué foto poner.

## 1. Flujo end-to-end (las 5 fases, todas en prod)

```
┌─ FASE A (H-070) ────────────────────────────────────────────────────────┐
│ Catálogo de fotos reales → modelo Clip + API ingesta con IA que propone │
│ taxonomía (área/nombre/momento/vapor/decoración/…) → operador confirma. │
└───────────────────────────────────────────────────────────────────────┘
                                    │
┌─ Brief semanal (LLM, fuera de M17 propiamente) ──────────────────────────┐
│ ventas/services/marketing_brief_generator.py::generate_brief()          │
│ → cada pieza con foto (gbp_post / slide de carrusel / historia del día) │
│   lleva un "criterio_foto" ESTRUCTURADO (no texto libre) que dice QUÉ    │
│   tipo de foto necesita esa pieza. Saneado/validado antes de persistir. │
└───────────────────────────────────────────────────────────────────────┘
                                    │ explode_brief_to_publicaciones()
                                    ▼
┌─ PublicacionPlanificada (+ segmentos) ───────────────────────────────────┐
│ Una fila por pieza de la semana. Las piezas con 2+ fotos (stories,       │
│ carrusel) llevan `segmentos`: una sub-entrada por historia/slide, cada   │
│ una con su propio `criterio_foto` + su propio material (foto final).    │
└───────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        ▼ (FASE B1, H-071)          ▼ (FASE 2, H-073)            ▼ (FASE 3, H-074)
  Explorador/ingesta manual   Auto-pick de 1 foto          Auto-pick EN LOTE
  (Angélica busca y elige)    ("🤖 Generar" por historia)   ("⚡ Generar las de hoy")
        │                           │                              │
        └──────────────┬────────────┴──────────────────────────────┘
                        ▼ (todas confluyen en el mismo paso)
        ┌─ Compositor B2-A (Cloudinary por URL, cero CPU) ────────┐
        │ foto elegida + texto + preset boutique → URL final      │
        │ (el preview ES el JPG que se descarga/publica)          │
        └──────────────────────────────────────────────────────────┘
                        │
                        ▼ "Enganchar" (ORM directo, sin re-subir)
        material_urls/material_meta del segmento + UsoClip (registro de uso,
        semilla del anti-repetición) + estado → 'lista' (NO 'publicada':
        Angélica revisa y sube a mano — nada se publica solo).
```

Las **3 formas de conseguir la foto** (manual / auto-1 / auto-lote) son intercambiables:
cualquiera de las 3 termina en el MISMO paso de "enganchar" — no hay 3 implementaciones
distintas del guardado, solo 3 formas distintas de LLEGAR a "qué clip usar".

## 2. Los 3 modelos (app `catalogo_clips`) y `PublicacionPlanificada` (app `marketing_briefs`)

### 2.1 `Clip` (catalogo_clips/models.py) — el catálogo de fotos reales

Campos **universales** (queryables, explícitos) + `atributos` (JSON libre para lo específico
del rubro — en Aremko, `{"hidromasaje": true}`):

| Campo | Tipo / choices | Para qué |
|---|---|---|
| `archivo` | Char, unique | Nombre original — clave de upsert en la ingesta. |
| `cloud_url` | URL | Cloudinary de la imagen **optimizada** (nunca el master pesado). |
| `tipo` | `foto\|video` | Fase A opera solo `foto`; el campo ya existe para video futuro. |
| `area` | `tina\|masaje\|cabaña\|entorno\|detalle\|aereo\|recepcion\|entorno_region` | Zona de la foto — filtro DURO del auto-pick. |
| `nombre_comercial` | Char, blank | Nombre del espacio puntual (p.ej. una tina o cabaña con nombre propio). `""` = "cualquiera de esa área sirve". |
| `momento` | `dia\|atardecer\|noche\|indistinto` | Se relaja en la cascada del auto-pick (nivel 3). |
| `estacion` | `invierno\|verano\|indistinto` | Hoy no la usa el auto-pick (solo el explorador manual). |
| `vapor` | `no\|sí\|sí (IA)` | `sí`/`sí (IA)` cuentan igual para el filtro `vapor_preferido`. |
| `decoracion` | `con\|sin\|""` | Se relaja en la cascada (nivel 3), como `momento`. |
| `personas` | Bool | Filtro DURO — solo se relaja en el último nivel (5) y con aviso explícito. |
| `permiso` | `libre\|revisar_derechos` | `personas=true` fuerza `revisar_derechos` (regla de saneo). |
| `calidad` | `alta\|media` | Informativo, no filtra el auto-pick hoy. |
| `keeper` | Bool | "Hero": sin personas, nítida, distinta. Preferencia del auto-pick (nivel 1), no obligación (nivel 2+). |
| `estado` | `ok\|revisar\|descartado` | **Filtro DURO en TODA la cascada, sin excepción** — nunca sale una foto no-`ok` por auto-pick. |
| `ultimo_uso` | Date, null | Desnormalizado — última vez que se usó en una historia. Motor del anti-repetición. |
| `etiquetas`, `apto_para` | JSON list | Libres, hoy informativos (no filtran auto-pick). |

**Puerto multi-tenant:** en Aremko quedó documentado pero SIN crear un FK `empresa` (mono-tenant).
En DH esto se resuelve con el FK `tenant` estándar de la plataforma.

### 2.2 `UsoClip` (catalogo_clips/models.py) — semilla del anti-repetición

```python
clip = FK(Clip, related_name='usos')
fecha = DateField()
publicacion_id = PositiveIntegerField(null=True)  # ver nota abajo
canal = CharField()
creado = DateTimeField(auto_now_add=True)
```

**Decisión a NO copiar literal:** `publicacion_id` es una **referencia SUAVE** (no `ForeignKey`)
a `PublicacionPlanificada` — fue una decisión defendida explícitamente para no romper el
aislamiento "drift-safe" de `catalogo_clips` en **Aremko**, un repo con arrastre de migraciones
roto (AR-033/AR-034) que no existe en DH. **En DH, con un sistema de migraciones sano, lo
correcto es un FK real** (tenant-scoped) entre `UsoClip`/`Clip` y el modelo de publicación de DH
— no hay motivo para preservar la referencia suave ahí. Es la ÚNICA decisión de diseño de este
dossier que se invierte a propósito en el traspaso.

### 2.3 `PublicacionPlanificada` (marketing_briefs/models.py) — la cola de trabajo semanal

Campos clave: `semana_inicio`/`dia` (fechas), `canal`/`tipo`/`pieza_key` (identidad de la
pieza), `copy_json` (la pieza completa del brief, shape variable según tipo), `estado`
(`pendiente|en_produccion|lista|publicada|no_aplica`), `material_urls`/`material_meta`
(para piezas de **una sola imagen**), `segmentos` (para piezas de **2+ imágenes** — stories,
carrusel).

**Shape de un item de `segmentos`:**
```json
{
  "indice": 1, "titulo": "Historia 1", "texto": "Texto de la historia",
  "criterio_foto": {"area": "tina", "nombre_comercial": "", "vapor_preferido": true,
                     "decoracion": "sin", "momento": "noche"},
  "material_urls": ["https://res.cloudinary.com/.../historia.jpg"],
  "material_meta": [{"url": "...", "tipo": "historia", "width": 1080, "height": 1920,
                      "ratio": "9:16", "orientacion": "vertical",
                      "receta": {"texto": "...", "posicion": "abajo", "preset": "velo",
                                 "clip_id": 42, "tipo": "historia"}}],
  "revision_veredicto": "sin_revisar", "revision_json": [], "revision_resumen": "", "revision_at": null
}
```

**Convención importante (no obvia, causó un bug real — ver §4):** `material_urls`/
`material_meta` son **listas que ACUMULAN historial** — cada "enganche" hace `append`, nunca
`replace`. **El último elemento (`[-1]`) es SIEMPRE el vigente**; los anteriores quedan como
auditoría (útil sobre todo para el flujo de revisión de video, donde Angélica sube varios
intentos). Cualquier código que lea "la foto de esta historia" debe leer `[-1]`, no `[0]`.

Restricción única: `UniqueConstraint(semana_inicio, pieza_key)` — el explode es **idempotente**:
re-correr sobre la misma semana solo actualiza piezas que siguen en `pendiente`/`no_aplica`
(nunca pisa lo que el operador ya movió de estado).

## 3. Servicios/lógica — PORTABLES TAL CUAL (sin acoplamiento a Aremko)

Estos archivos/funciones no tienen NADA específico de Aremko — dependen solo de los 3 modelos
de arriba (con sus mismos campos) y pueden copiarse con cambios mínimos (imports, tenant scope):

- **`catalogo_clips/composer.py`** — `receta_normalizada()` + `url_historia()`. Renderiza la
  historia **encadenando transformaciones en la URL de Cloudinary** — cero CPU propia, cero
  timeout, el preview ES el JPG final. Dos trampas de sintaxis Cloudinary ya resueltas
  empíricamente (bisectadas contra el cloud real, no adivinadas — ver §5).
- **`catalogo_clips/seleccionar.py`** — `seleccionar_clip(criterio, dias=60,
  permitir_personas=False, excluir_ids=None) -> (clip, nivel, aviso)`. El auto-pick
  determinista: cascada de 6 niveles de degradación (keeper+fresca → sin keeper → relaja
  momento/decoración → permite repetir → permite personas → nada), cada nivel con un `aviso`
  auditable. `area`/`nombre_comercial`/`vapor_preferido`/`estado='ok'` son duros en TODA la
  cascada — nunca se relajan.
- **`catalogo_clips/web_views.py::_elegir_diverso`** — envuelve `seleccionar_clip` para el modo
  batch: intenta (hasta 4 veces) no repetir `nombre_comercial` entre historias con un criterio
  genérico dentro de un mismo lote, degradando a repetir si no hay stock. Deseable, no
  obligatorio — nunca hace fallar el ítem.
- **`ventas/services/marketing_brief_generator.py::_sanear_criterio_foto` /
  `_sanear_criterios_foto`** — defensa en profundidad: valida el `criterio_foto` que propone el
  LLM contra los enums reales ANTES de persistirlo (lo descarta entero si `area` no calza). Es
  una función pura (ni siquiera toca el ORM) — se copia literal, solo hay que mantener el set de
  enums sincronizado con los `choices` reales de `Clip` en DH.

## 4. Lo que NECESITA adaptación (no copiar literal)

- **`catalogo_clips/tagging.py::TAGGING_SYSTEM_PROMPT`** — la taxonomía (nombres exactos de
  tinas/cabañas de Aremko, reglas de vapor, etc.) está **hardcodeada en el prompt**, a propósito
  (ver `BRIEF_H-070` §3: es la única forma de que la IA proponga bien la taxonomía real de un
  negocio puntual). **En DH esto debe volverse configurable por tenant** — probablemente un
  bloque de taxonomía en la config del tenant que se inyecta al armar el prompt, en vez de un
  string fijo en el código.
- **Multi-tenant real:** los 3 modelos necesitan el FK `tenant` de DH (Aremko lo dejó
  documentado pero sin crear). Todos los querysets de `seleccionar_clip`/vistas/admin deben
  filtrar por tenant.
- **Auth/gating:** `@staff_member_required` (admin de Django) → el propio esquema de DH
  (`@requires_feature` + `apps/entitlements`). Registrar el módulo en la tabla `Modulo` +
  `docs/MODULOS.md` de DH.
- **`UsoClip.publicacion_id`** → FK real en DH (ver §2.2 — es la excepción a "portar tal cual").
- **El generador completo del brief** (`marketing_brief_generator.py`) tiene mucho código
  específico de Aremko (fetch de GA4/GSC/Meta/Google Ads propios, pipeline de reservas interno,
  doc del playbook local). **Solo la parte de schema/sanitizer de `criterio_foto` es
  genéricamente portable** (§3) — el resto de "fuentes" es exactamente lo que
  `MIGRACION_M17_A_DH.md` describe como "enchufes por tenant" (§1-2 de ese doc): en DH se
  arma de nuevo, alimentado por LAS fuentes de cada tenant (para Cabañas PV: sus propias
  reservas/reseñas/etc. ya viven en DH).
- **URLs/namespaces** (`/marketing/catalogo/`, `/marketing/publicaciones/`) → bajo
  `apps/publicaciones` con el esquema de rutas propio de DH.

## 5. Gotchas empíricos (para no re-descubrirlos a las malas)

1. **Cloudinary — texto + posición van en componentes SEPARADOS.** Combinar
   `l_text:...,w_860,c_fit,g_south,y_380` en un solo string da HTTP 400. Hay que partir la
   posición (`g_south,y_380`) en un `fl_layer_apply` propio, después de la capa de texto.
2. **Cloudinary — `letter_spacing_N` va DENTRO del string de la fuente**
   (`Montserrat_26_letter_spacing_6_center`), no como parámetro separado por coma.
3. **Postgres ordena NULLs AL FINAL por default en `ASC`.** Para que "nunca usado"
   (`ultimo_uso=None`) salga PRIMERO en el auto-pick (más fresco que cualquier fecha), hay que
   pedir `F('ultimo_uso').asc(nulls_first=True)` explícito — el default hace lo contrario de lo
   que uno espera.
4. **"Último = vigente"** es la convención en TODA lista de material acumulado (a nivel
   segmento y a nivel pieza). Un bug real (H-074) fue leer `urls[0]` en vez de `urls[-1]` para
   la miniatura — "re-generar reemplaza" no se veía reflejado en pantalla aunque el dato ya
   quedara correcto.
5. **Ingesta de fotos:** HEIC (default del iPhone) se rechaza — hay que convertir a JPG antes.
   Master >16 MB se rechaza — optimizar antes de subir. `estado` solo acepta
   `ok|revisar|descartado` literal.
6. **Anti-repetición dentro de un lote batch:** `excluir_ids` se acumula y se pasa COMPLETO en
   cada iteración — si dos historias del mismo lote piden un criterio para el que solo existe
   1 foto, la SEGUNDA no repite esa foto (va a "Manual" en vez de repetir) — es la semántica
   correcta según el diseño acordado, no un bug.

## 6. Historial completo (los 5 handoffs, todos LIVE y con tests)

| Fase | Handoff | Qué construyó | Doc |
|---|---|---|---|
| A | H-070 | `Clip` + API ingesta (4 endpoints, `X-API-KEY`) + etiquetado IA | `BRIEF_H-070_catalogo_clips_fase_a.md` + `CONTRATO_H-070_CATALOGO.md` |
| B1 | H-071 | Explorador/ingesta web staff (server-rendered, sin API key — sesión) | `BRIEF_H-071_catalogo_clips_fase_b1_explorador.md` |
| 1 | H-072 | Pantalla "Publicaciones" + puente al compositor + enganche ORM + `UsoClip` | `BRIEF_H-072_m17_historias_fase1_manual_puente.md` |
| 2 | H-073 | `criterio_foto` en el brief + `seleccionar_clip` (auto-pick 1 foto) + botón "🤖 Generar" | `BRIEF_H-073_m17_historias_fase2_autopick.md` |
| 3 | H-074 | Batch "⚡ Generar las de hoy" + `_elegir_diverso` + fix `urls[-1]` | `BRIEF_H-074_m17_historias_fase3_batch.md` |

Cada doc tiene el diseño acordado + el checklist de cierre real. `docs/HANDOFFS.md` (este repo)
tiene el estado 🟢/🟡 de cada uno y las notas de verificación e2e en prod con datos reales.

## 7. Qué NO existe todavía (fuera de alcance de H-070…H-074)

- **Carrusel/reel con auto-pick** — el modelo YA soporta `segmentos` para carrusel (H-063/H-066
  ya explotan slides/tomas a segmentos), pero el auto-pick (Fases 2-3) solo se activó para
  **stories**. Activarlo para carrusel es mecánico (mismo `criterio_foto`/`seleccionar_clip`)
  pero no se hizo — no hacía falta en Aremko todavía.
- **Chat de ajuste** (pedir "más luz", "otra hora del día" en lenguaje natural) — no construido.
- **Video** (auto-pick de clips de video, no solo fotos) — H-065/H-066 ya tienen revisión IA de
  video y frames por URL (mismo patrón `so_<seg>` de Cloudinary), pero el auto-pick de fotos NO
  se extendió a video.

Todo esto corresponde a **M-2** según `MIGRACION_M17_A_DH.md` §3 — no a M-1 (que es "portar lo
que ya funciona", no agregar features nuevas).

## 8. Preguntas abiertas para resolver JUNTOS en el plan de M-1

1. **Taxonomía por tenant:** ¿tabla de configuración editable, o seguir con `choices` fijos +
   `atributos` JSON libre (como hoy) pero con el prompt de `tagging.py` armado dinámicamente
   desde esa config?
2. **`UsoClip.publicacion_id`:** ¿FK real directo al modelo de publicación de DH (recomendado,
   ver §2.2) o se prefiere mantener alguna capa de desacople por otro motivo del lado DH?
3. **Alcance exacto de M-1:** ¿se porta TODO (Fases A + B1 + 1 + 2 + 3) de una vez, o se
   escalona (ej. primero Fase A+1 manual, después 2-3 auto-pick)? Este dossier alcanza para
   cualquiera de los dos escenarios.
4. **Dónde vive el generador del brief en DH** — en Aremko vive en `ventas/services/` (fuera de
   la app aislada `marketing_briefs`, ver nota en `BRIEF_H-073`); en DH probablemente conviene
   que viva DENTRO de `apps/publicaciones` (el "motor" completo en un solo lugar) ya que ahí no
   hay el problema de drift que forzó esa separación en Aremko.
