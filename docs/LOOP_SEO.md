# Loop de mejora continua — SEO (aremko.cl)

> Bitácora del loop dedicado (sesión propia, `/loop`, semanal) que revisa el
> tráfico orgánico y posicionamiento de **aremko.cl únicamente** (destinopuertovaras.cl
> queda fuera por ahora) y propone acciones SEO concretas. Cada ciclo LEE este
> archivo antes de proponer algo nuevo y AGREGA su entrada al final. Hermano de
> `docs/LOOP_META_ADS.md`/`LOOP_GOOGLE_ADS.md` del repo aremko-cli (mismo
> espíritu: Nivel 2, bitácora, comparación ciclo a ciclo), pero **separado** del
> brief semanal de marketing que ya existe (`generate_weekly_marketing_brief`,
> lunes 10am) — ese sigue igual, este es nuevo y enfocado solo en SEO accionable.

## Reglas de autonomía (definidas con Jorge, 2026-07-02)

- **Nivel 2: SOLO PROPONE.** El loop NUNCA publica contenido, NUNCA edita
  `SEOContent`/`HomepageConfig`/`BlogPost` en la base de datos directamente, y
  NUNCA marca un `BlogPost` como publicado. Sus "arreglos" son **texto
  propuesto en esta bitácora** (título, meta_description exacta, outline o
  borrador completo de un post) — Jorge (o una sesión interactiva) los aplica
  a mano en el admin cuando decide. Esto es MÁS conservador que "guardar un
  borrador sin publicar" a propósito: evita darle al loop escritura directa a
  la base de datos de producción sin necesidad.
- **⚠️ Las primeras 7 semanas de GSC en el endpoint son CERO — es un hueco
  histórico, NO una caída real de tráfico.** La cuenta de servicio recién
  obtuvo permiso de Search Console el 2026-07-02 (antes tenía acceso a GA4 pero
  NO a Search Console — son espacios de permiso separados en Google aunque sea
  la misma cuenta). Ignorar comparaciones de clicks/impressions/position de
  semanas anteriores al 2026-07-02 — tratarlas como "sin dato", no como "cero
  real". La comparación semana-a-semana de GSC recién es confiable desde esa
  fecha en adelante (se va llenando solo, una semana más cada lunes).
  **GA4 en cambio SÍ tiene historial real completo (8/8 semanas) desde el
  principio — usarlo con confianza para tendencias de sesiones/conversiones.**
- **Keywords protegidas** (de `docs/SEO_BASELINE_HOME.md`) — vigilar su
  posición/clics en cada ciclo: `masajes puerto varas`, `tinajas puerto varas`
  (con J, no confundir con "tinas"), `spa puerto varas`, y marca (`aremko`,
  `aremko spa`, `aremko aguas calientes puerto varas`).

## Palancas de arreglo (para redactar propuestas concretas, no genéricas)

- `SEOContent` (admin `/admin/ventas/seocontent/`) — `meta_title` (≤70 char)
  y `meta_description` (≤160 char) por categoría (Tinas, Masajes, Alojamientos).
- `HomepageConfig` (admin `/admin/ventas/homepageconfig/`) — textos del home
  (hero, filosofía, CTA). Ver `docs/SEO_BASELINE_HOME.md` antes de tocar nada
  del home — tiene una lista de "qué NO perder" del rediseño 2026-06-28.
- `BlogPost` (admin `/admin/aremko_blog/blogpost/`) — clusters: TINAS, MASAJES,
  SPA, ROMANCE, RIO, BOUTIQUE. Campos: `title`, `slug`, `meta_description`,
  `keyword_root`, `intro`, `body_md`, `cta_text`/`cta_url`. Recordar la regla
  de voz/humor obligatorio del blog (no genérico, con personalidad).

## Fuente de datos externa — DataForSEO, vía aremko-cli (rankings reales + competidores)

> Agregado 2026-07-06, migrado a endpoints de aremko-cli el mismo día. GA4/GSC
> dicen cómo le va a **Aremko**; nunca muestran quién aparece ARRIBA en Google.
> DataForSEO llena ese hueco. Cuenta paga por uso (dataforseo.com), fondeada
> por Jorge — pero ya NO se llama directo con credenciales locales: hay 3
> endpoints en el backend de aremko-cli (Render, credenciales server-side +
> cache 12-24h) que hacen de proxy. Igual que `seo-snapshots` de Django: sin
> auth, sin token, sin Keychain que gestionar desde este loop.

```bash
# Rankings (usa la lista fija de 9 keywords por defecto — ver abajo)
curl "https://aremko-cli-backend.onrender.com/api/v1/seo/rankings"

# Backlinks — mensual, no cada ciclo (el cache ya lo protege, pero no hace
# falta pedirlo si no aporta nada nuevo esta semana)
curl "https://aremko-cli-backend.onrender.com/api/v1/seo/backlinks"

# Competidores por solapamiento de keywords — on-demand, al evaluar un tema
# de contenido nuevo (p.ej. antes de proponer un BlogPost)
curl "https://aremko-cli-backend.onrender.com/api/v1/seo/competitors"
```

`/rankings` devuelve, por keyword: `found` (bool), `position` (posición
ORGÁNICA, 1-indexed — cuenta solo resultados `type=organic`, no bloques como
knowledge graph/imágenes/local pack), `rank_absolute` (posición absoluta en
el SERP completo, referencia, no comparar ciclo a ciclo), `url`, y
`competitors_above` (hasta 10 dominios orgánicos que salen antes que
aremko.cl — información que Search Console nunca da). El backend cachea 12h,
así que llamarlo en cada ciclo no tiene costo adicional si ya se llamó ese
día por otro motivo (ej. Jorge abrió el dashboard `/dashboard/jorge/seo`).

**⚠️ Fix aplicado 2026-07-06 (sesión interactiva) — leer antes de comparar
contra ciclos anteriores al 2026-07-06:**
- **Ubicación:** el default era `location_name: "Chile"` (país completo) →
  corregido a `"Puerto Varas,Los Lagos,Chile"` (DataForSEO `location_code
  1003309`, confirmado real vía `/v3/serp/google/locations/CL`). Los ciclos
  antes de esta fecha comparaban contra un rank-check nacional/genérico, no
  contra lo que ve alguien buscando desde/sobre Puerto Varas — no comparables
  1:1 con los ciclos posteriores.
- **Cálculo de posición:** antes usaba `rank_absolute` directo (cuenta TODOS
  los bloques del SERP). Confirmado en producción con la keyword "aremko":
  `rank_absolute=2` pero era el Knowledge Graph ocupando el puesto 1 —
  aremko.cl SÍ era el #1 orgánico real. Ahora `position` cuenta solo
  orgánicos; `rank_absolute` se guarda aparte como referencia.
- Código: `aremko-cli/backend/internal/api/handlers/dataforseo.go` (constante
  `seoDefaultLocationName`) y `internal/dataforseo/queries.go` (struct
  `RankCheckResult`, función `getSingleRankCheck`).
- **Hallazgo real (no bug) descubierto en la misma revisión:** para "spa
  puerto varas" con ubicación correcta, Aremko **no aparece en el Local
  Pack** (mapa de Google, 3 fichas) — lo ocupan `energiavitalpv`, Instagram y
  `santocha.cl`. Vale la pena revisar el Google Business Profile de Aremko en
  algún ciclo futuro (fuera del alcance de este fix).

**Lista fija de keywords trackeadas** (vive como default en
`backend/internal/api/handlers/dataforseo.go` → `seoDefaultKeywords` del repo
aremko-cli; mirror acá solo de referencia — cambiarla requiere editar ESE
archivo Go y redeployar, no algo que el loop haga solo):
`spa puerto varas`, `masajes puerto varas`, `tinajas puerto varas`, `termas
puerto varas`, `termas en puerto varas`, `cabaña con tina caliente puerto
varas`, `escapada romántica puerto varas`, `spa cerca de puerto varas`,
`aremko`. (9 keywords desde 2026-07-08 — se agregó `spa cerca de puerto
varas` tras descubrir que Aremko ya rankea #3 ahí, ver sección de
competidores abajo.)

### Historial persistido de rank-check (nuevo 2026-07-06)

El endpoint `/rankings` de arriba solo da la foto del momento (cache 12h, se
pierde en cada redeploy de Render) — no permite ver evolución en el tiempo.
Para eso existe ahora, en este mismo repo Django, un historial persistido:

```bash
curl "https://www.aremko.cl/ventas/api/aremko-cli/seo-rankings-history/?weeks=8"
```

Devuelve `{"weeks_requested": N, "targets": [...], "rankings": {"<dominio>":
{"<keyword>": [{fetched_at, found, position, rank_absolute, url,
competitors_above}, ...], ...}, ...}}`, más antiguo primero por keyword.
Filtrar a un solo dominio con `?targets=aremko.cl`. Público, sin auth (mismo
criterio que `seo-snapshots`). Es SOLO LECTURA de lo que ya guardó
`sync_aremko_cli_seo_rankings` (app aislada `aremko_cli_sync`, modelo
`SEORankingSnapshot`, drift-safe respecto a `ventas`) — no genera nada nuevo.

**Este endpoint solo tiene datos si alguien corrió el sync.** Disparo:
`python manage.py sync_aremko_cli_seo_rankings` (a mano), o vía el cron
`POST /ventas/api/cron/sync-seo-rankings/` (header `X-API-KEY`) — **cron ya
configurado por Jorge en cron-job.org**, lunes 09:10 hora Chile (10 min
después de `snapshot-weekly-traffic`, antes de que despierte el loop). Cada
corrida ahora sincroniza Aremko + los 3 competidores de la sección de abajo
(36 filas por corrida: 4 dominios × 9 keywords, desde que se agregó "spa
cerca de puerto varas" — antes eran 32 con 8 keywords).

### Competidores trackeados (nuevo 2026-07-08)

Además de Aremko, `sync_aremko_cli_seo_rankings` corre el MISMO rank-check
(las mismas 9 keywords protegidas) contra 3 competidores directos —
confirmados 2026-07-08 tras analizar un video tutorial de Semrush One sobre
SEO+AEO. Lista editable en `DEFAULT_TARGETS` del management command (agregar
uno nuevo no requiere tocar aremko-cli ni cron-job.org, el endpoint
`/api/v1/seo/rankings` ya acepta `?target=` para cualquier dominio):

- **cancagua.cl** — Cancagua Spa & Retreat Center, biopiscinas geotermales en
  Frutillar. El competidor más parecido al modelo de Aremko (spa boutique,
  no termas naturales remotas).
- **termasdelsol.com** (ojo: NO `.cl`) — Termas del Sol, 10 piscinas
  termales volcánicas en Río Puelo, Patagonia. "Ritual Patagónico"
  autoguiado.
- **termascochamo.com** (ojo: sin "s", NO `termascochamos.com`) — Termas
  Cochamo, termas naturales en Cochamó. Ya lo teníamos identificado como
  `competitors_above` en las keywords de "termas".

**Baseline comparativo 2026-07-08** (backlinks vía `/api/v1/seo/backlinks?target=`,
rank-check vía `/api/v1/seo/rankings?target=`):

| Dominio | Backlinks | Dominios referentes | Rank |
|---|---:|---:|---:|
| aremko.cl | 26 | 20 | 92 |
| cancagua.cl | 117 (4.5x) | 44 (2.2x) | 134 |
| termasdelsol.com | 271 (10x) | 192 (9.6x) | 157 |
| termascochamo.com | 86 (3.3x) | 49 (2.4x) | 109 |

Los 3 competidores superan a Aremko en autoridad de enlaces — oportunidad de
link building a evaluar en un ciclo futuro.

| Keyword | aremko.cl | cancagua.cl | termasdelsol.com | termascochamo.com |
|---|---|---|---|---|
| `aremko` | **1** | — | — | — |
| `tinajas puerto varas` | **1** | — | — | — |
| `cabaña con tina caliente puerto varas` | 2 | — | — | — |
| `masajes puerto varas` | 3 | — | — | — |
| `spa puerto varas` | 7 | — | — | — |
| `termas en puerto varas` | 8 | — | 3 | **1** |
| `termas puerto varas` | 9 | — | 3 | **1** |
| `escapada romántica puerto varas` | 17 | — | — | — |

**Hallazgo clave: Cancagua no aparece en NINGUNA de las 8 keywords
protegidas.** No es que sea débil — compite en un espacio de keywords
distinto (probablemente algo como "spa frutillar", "biopiscinas frutillar",
"spa los lagos") que hoy no chequeamos. Es un punto ciego real de la lista
fija, no una ausencia real de competencia. Termas del Sol y Termas Cochamó sí
compiten, pero SOLO en el clúster "termas" — confirma que el post de termas
publicado el 2026-07-02 atacó la oportunidad correcta.

**Próximo paso pendiente (no implementado aún):** un "Keyword Gap" real —
descubrir automáticamente qué keywords rankean Cancagua/Termas del Sol/Termas
Cochamó que Aremko ni siquiera está chequeando hoy, en vez de solo comparar
contra la lista fija de 8. Requeriría un endpoint nuevo en `aremko-cli`
(DataForSEO Labs `domain_intersection` o similar) — evaluar si vale la pena
antes de construirlo, o probar primero algunas keywords candidatas a mano
(ej. "spa frutillar", "biopiscinas frutillar", "spa los lagos").

También pendiente y fuera del alcance de DataForSEO: **AEO real** — si
Aremko aparece cuando alguien le pregunta a ChatGPT/Perplexity/Gemini/AI
Overview de Google sobre tinas o spa en Puerto Varas, comparado contra estos
3 competidores. Hoy no hay visibilidad de esto (gap total, confirmado al
analizar el video de Semrush — su tool "AI Visibility Overview" cubre
exactamente esto). Evaluar en un ciclo futuro si se construye algo propio o
se paga una herramienta dedicada.

**Competidores reales detectados hasta ahora** (aparecen arriba de aremko.cl en
al menos 1 keyword protegida, verificado 2026-07-06 con datos reales):
`wyndhampettra.com`, `hotelbellavista.cl`, `hotelcabanadellago.cl`,
`puerto-varas.dreams.cl`. Si uno se repite en varias keywords o sube, vale la
pena pedir `/seo/competitors` y revisar su backlink profile para entender por
qué gana.

Hay también un dashboard visual de esto en `/dashboard/jorge/seo` (aremko-cli
frontend) — Jorge puede revisarlo directamente sin esperar al ciclo semanal.

## Qué hacer en cada ciclo

1. Leer la última entrada de este archivo (qué se propuso, si Jorge respondió algo).
2. Traer los últimos 8 snapshots semanales (GA4 + GSC ya guardados, no generar nada nuevo):

   ```
   curl "https://www.aremko.cl/ventas/api/aremko-cli/seo-snapshots/?weeks=8"
   ```

   Sin auth, sin token. Aplicar la regla de arriba sobre semanas GSC en cero.

3. Rank check con DataForSEO vía aremko-cli (ver sección de arriba):

   ```
   curl "https://aremko-cli-backend.onrender.com/api/v1/seo/rankings"
   curl "https://www.aremko.cl/ventas/api/aremko-cli/seo-rankings-history/?weeks=8"
   ```

   Comparar cada posición contra lo que reporta GSC para las keywords
   protegidas, y anotar qué dominios aparecen arriba en cada una. Usar el
   historial (segundo curl) para ver tendencia real semana a semana en vez
   de solo la foto del momento — puede venir vacío o corto si el cron de
   sync todavía no está configurado (ver sección de arriba).
4. Opcional, para ver si el tráfico orgánico se traduce en negocio real (mismo
   criterio "no confiar solo en la plataforma" que los loops de ads, aunque acá
   el vínculo es más indirecto que en ads):

   ```
   curl "https://www.aremko.cl/ventas/api/aremko-cli/bookings/family-combinations-range/?date_start=<inicio semana>&date_stop=<fin semana>"
   ```

5. Comparar contra la última entrada de la bitácora: ¿subió/bajó el tráfico
   orgánico?, ¿alguna keyword protegida perdió posición (en GSC o en el rank
   check de DataForSEO)?, ¿algún `top_query` nuevo con volumen que no tiene
   contenido dedicado?, ¿algún competidor nuevo apareció arriba de Aremko?
6. Producir 1-3 recomendaciones NUEVAS y concretas — preferí propuestas
   REDACTADAS (el meta_description exacto, el título del post, el outline)
   sobre sugerencias vagas tipo "mejorar el SEO de X".
7. Agregar una entrada nueva al FINAL de este archivo con: fecha, snapshot
   corto (tráfico GA4 + GSC de la semana, keywords protegidas, rank check
   DataForSEO), y las recomendaciones redactadas. Commitear (solo este .md)
   con mensaje en español.
8. Nivel 2 — SOLO PROPONER: no editar modelos de Django, no publicar nada. Solo
   proponer texto en la bitácora y esperar la respuesta de Jorge.

---

## Bitácora de ciclos

### Ciclo 1 — 2026-07-02 (primera corrida)

**Snapshot GA4 (historial real, 8 semanas — sesiones TOTALES, todos los canales):**

| Semana | Sesiones | Conv | Engagement | Dur.media | Reservas iniciadas |
|--------|---------:|-----:|-----------:|----------:|-------------------:|
| 05-25  | 693  | 46 | 56% | 192s | 205 |
| 06-01  | 950  | 30 | 47% | 135s | 156 |
| 06-08  | 1386 | 63 | 41% | 176s | 170 |
| 06-15  | 1541 | 89 | 46% | 123s | 123 |
| 06-22  | 1079 | 53 | 52% | 185s | 170 |
| **06-29** | **805** | **72** | **61%** | **237s** | **243** |

- ⚠️ **El pico de sesiones jun 8–22 NO es crecimiento SEO**: coincide con la
  campaña Meta de GiftCard Día del Padre (corrió 11/06–22/06). Son sesiones
  pagadas, no orgánicas. Al terminar la campaña las sesiones bajaron a 805.
- La semana más reciente (06-29), pese a menos sesiones totales, muestra la
  **mejor calidad de tráfico de toda la serie**: engagement 61% (máx.),
  duración media 237s (máx.), 243 reservas iniciadas (máx.) y 72 conversiones
  (rebota desde 53). Consistente con tráfico orgánico/directo de mayor intención
  una vez apagado el pago. Salud orgánica: buena, no en caída.
- Contexto de negocio (opcional): semana 22–28 jun = 54 reservas / $5.07M.

**Snapshot GSC — PRIMERA semana con dato real (2026-07-02):**

- Total: **242 clicks, 2.526 impresiones, CTR 9.58%, posición media 6.37.**
- Esto es el **baseline**: las 7 semanas previas están en cero por el hueco de
  permiso (H-057), son "sin dato". Recién el próximo lunes habrá comparación
  semana-a-semana confiable.

**Keywords protegidas (baseline):**

- `masajes puerto varas` → pos **2.26** ✅ (4 clk / 35 imp)
- `tinajas puerto varas` (con J) → pos **2.92** ✅ (10 clk / 78 imp, CTR 12.8%)
- `spa puerto varas` → **no aparece en el top** ⚠️; solo `spa en puerto varas`
  pos 4.73 (3 clk / 26 imp) y `spa masajes puerto varas` pos 1. La cabeza exacta
  "spa puerto varas" está sub-rankeada — a vigilar.
- Marca (`aremko` pos 1.2 / 75 clk, `aremko spa` pos 1.06, `aremko aguas
  calientes puerto varas` pos 1.25) → **domina** ✅.

**Hallazgos accionables detectados:**

1. **Clúster "termas" sin contenido dedicado y sub-rankeado** (mayor oportunidad
   no-marca): `termas puerto varas` pos 4.83 (90 imp), `termas en puerto varas`
   pos 7.44 (63 imp), `mejores termas en puerto varas` pos 6.75. ~157 impresiones
   no-marca cayendo en la home a media/segunda página, sin un post que atrape esa
   intención. No existe post de "termas" (solo hay blog de tinas, masajes y
   escapada-romántica).
2. **`/masajes/` con volumen y CTR bajo**: 543 imp, pos 5.77, CTR 2.9%. Meta
   description genérica ("Terapeutas certificados. Reserva online").
3. **`tinajas en puerto varas` (con "en") en página 2**: pos 11.59 (34 imp),
   mientras `tinajas puerto varas` (sin "en") rankea 2.92. El blog
   `/blog/tinas-calientes-puerto-varas/` tiene 298 imp pero CTR ~0.34% (pos 6.41):
   su meta dice "tinas" y la gente busca "tinajas" (con J) y "termas".

---

#### Recomendaciones NUEVAS (Nivel 2 — SOLO PROPUESTA, aplica Jorge en admin)

**REC 1 — Crear BlogPost nuevo para el clúster "termas" (`BlogPost`, cluster TINAS o BOUTIQUE).**
Intención de búsqueda real que hoy Aremko no ataca con contenido propio.

- `title` / H1: **¿Termas en Puerto Varas? La verdad sobre las aguas calientes junto al río** (73 char; si el `<title>` = title, usar meta_title corto abajo)
- `meta_title` (≤70): **Termas en Puerto Varas: la verdad | Aremko Spa Boutique** (55 char)
- `slug`: `termas-puerto-varas`
- `keyword_root`: `termas puerto varas`
- `meta_description` (151/160): **¿Buscas termas en Puerto Varas? No hay termas naturales cerca, pero sí tinajas de agua caliente junto al río Pescado, a 40°, abiertas hasta medianoche.**
- Outline propuesto (con la voz/humor obligatorio del blog):
  1. Intro con gancho honesto y con humor: buscás "termas en Puerto Varas" y la
     mala noticia es que las termas naturales quedan lejos (Puyehue ~1h, Ralún);
     la buena, que hay algo mejor a 5 min del centro.
  2. H2 · *¿Hay termas naturales en Puerto Varas?* — honestidad SEO: las termas
     naturales más cercanas y por qué no son plan de una tarde.
  3. H2 · *La alternativa urbana: tinajas de agua caliente junto al río* — 40°,
     aerotermia + paneles solares, sin azufre, río Pescado al lado.
  4. H2 · *Termas vs tinajas: cuál te conviene* — tabla corta según lo que busca
     el visitante (naturaleza remota vs. ritual boutique en la ciudad).
  5. H2 · *Cómo reservar tu tina* — horarios hasta medianoche, oferta dom-jue.
  6. CTA: reservar tina (`cta_text`: "Reserva tu tina junto al río" → `/tinas/`).

**REC 2 — Reescribir meta de la categoría Masajes (`SEOContent` → Masajes).**
Levantar CTR sobre 543 imp/semana; diferenciar con "junto al río / tina opcional".

- `meta_title` (58/70): **Masajes en Puerto Varas junto al río | Aremko Spa Boutique**
- `meta_description` (151/160): **Masajes descontracturantes, relajantes y con piedras calientes en Puerto Varas, junto al río Pescado. Terapeutas certificados y tina caliente opcional.**
- (Actual: "Masajes profesionales en Puerto Varas: relajantes, descontracturantes,
  con piedras calientes y aromaterapia. Terapeutas certificados. Reserva tu sesión online.")

**REC 3 — Ajustar meta_description del BlogPost de tinas (`/blog/tinas-calientes-puerto-varas/`).**
Incorporar la grafía que la gente busca ("tinajas" con J) y "termas" para capturar
`tinajas en puerto varas` (hoy pos 11.59, página 2) y subir el CTR (~0.34%).

- `meta_description` propuesta (158/160): **Tinajas de agua caliente en Puerto Varas (la alternativa a las termas): temperatura ideal, ritual, aerotermia + solar y horario hasta medianoche junto al río.**
- (Actual: "Guía práctica de tinas calientes en Puerto Varas: temperatura, tiempo,
  ritual, aerotermia + paneles solares, río Pescado al lado y horarios hasta medianoche.")

_Estado: revisado con Jorge en sesión interactiva (2026-07-02)._

#### Acciones aplicadas (sesión interactiva, 2026-07-02)

- ✅ **REC 2 APLICADA** — Jorge actualizó `SEOContent` → Masajes en el admin con
  el `meta_title` (58 char) y `meta_description` (151 char) propuestos.
  Verificado live en `https://www.aremko.cl/masajes/` (title + description
  renderizando los textos nuevos). Baseline a batir: 543 imp/sem, CTR 2.9%,
  pos 5.77 — el próximo ciclo debe comparar CTR de `/masajes/` contra esto.
- ✅ **REC 3 APLICADA** — Jorge actualizó el `meta_description` (158 char) del
  BlogPost `/blog/tinas-calientes-puerto-varas/` en el admin, incorporando
  "tinajas" (con J) y "termas". Verificado live. Baseline a batir: 298 imp,
  CTR ~0.34%, pos 6.41; y `tinajas en puerto varas` en pos 11.59 (página 2) —
  el próximo ciclo debe revisar si esa query sube de página y si el CTR mejora.
- ✅ **REC 1 APLICADA** — BlogPost `termas-puerto-varas` creado y publicado por
  Jorge en el admin (cluster TINAS, keyword_root `termas puerto varas`).
  El borrador se ajustó en revisión con Jorge respecto a lo propuesto:
  - Título más corto (56 char) porque el template agrega " · Aremko Spa
    Boutique" (+22) al `<title>`.
  - Datos corregidos por Jorge: son **tinas artesanales** (no "tinajas de
    madera nativa"), a **20 minutos** del centro (no 5), agua a **38-39°**
    (no 40°) con **garantía: a 37° o menos la tina es gratis** (quedó como
    bullet destacado — diferenciador único).
  - CTA final quedó "Reserva tu tinaja junto al río" → `/tinas/` (200 OK).
  Verificado live: 200, title/meta/4 H2/CTA renderizando y presente en
  `sitemap.xml`. Baseline a batir: `termas puerto varas` pos 4.83 (90 imp),
  `termas en puerto varas` pos 7.44 (63 imp) — hoy caen en la home; el próximo
  ciclo debe revisar si el post nuevo empieza a capturar esas queries y si
  aparece en top_pages.

**Ciclo 1 cerrado: 3/3 recomendaciones aplicadas el mismo día (2026-07-02).**

---

### Infraestructura — fix de DataForSEO + historial persistido (2026-07-06, sesión interactiva)

Jorge conectó DataForSEO a `aremko-cli` y encontró los resultados "malos" a
simple vista (comparado contra GSC). Diagnóstico + fix, sin esperar al ciclo
semanal porque afecta la fuente de datos de TODOS los ciclos futuros:

**Diagnóstico (confirmado con pruebas reales contra la API de DataForSEO, no
solo lectura de código):**
1. `location_name: "Chile"` (país) en vez de Puerto Varas específico — traía
   competidores/posiciones genéricas de todo el país.
2. Bug de cálculo: `position` usaba `rank_absolute` (cuenta TODOS los bloques
   del SERP — knowledge graph, imágenes, local pack, etc.), no solo
   orgánicos. Confirmado con "aremko": `rank_absolute=2` pero era el
   Knowledge Graph en el puesto 1 — aremko.cl SÍ era el #1 orgánico real.
3. Hallazgo real (no bug): Aremko no aparece en el Local Pack de Google Maps
   para "spa puerto varas" (si la ubicación es correcta) — a revisar en un
   ciclo futuro.

**Fix aplicado (repo `aremko-cli`, backend Go):**
- `backend/internal/api/handlers/dataforseo.go`: `seoDefaultLocationName` →
  `"Puerto Varas,Los Lagos,Chile"`.
- `backend/internal/dataforseo/queries.go`: `RankCheckResult.Position` ahora
  cuenta solo items `type=="organic"`; se agregó `RankAbsolute` como campo de
  referencia separado.
- Validado con `go build ./...`, `go vet` (limpio en los archivos tocados;
  el único warning de `go vet ./...` es preexistente en `internal/ai`, no
  relacionado) y `gofmt`. Sin tests que romper (no hay tests en esos paquetes).
- **Pendiente: Jorge debe confirmar el push de `aremko-cli` a `main`** (Render
  auto-deploya) — no se pusheó en esta sesión, solo se dejó listo localmente.

**Historial persistido nuevo (repo Django, este repo), para responder "cómo
evolucionan estas keywords en el tiempo" y no solo ver la foto del momento:**
- Modelo `SEORankingSnapshot` en app aislada `aremko_cli_sync` (drift-safe,
  mismo patrón que `WeeklyBriefSnapshot` — NO se tocó `ventas/models.py`,
  evita el drift AR-034 pendiente). Migración `aremko_cli_sync/migrations/
  0002_seorankingsnapshot.py`, generada y aplicada limpia en local (Docker).
- Management command `sync_aremko_cli_seo_rankings`: llama
  `aremko-cli:/api/v1/seo/rankings` y guarda 1 fila por keyword. Probado en
  vivo contra el aremko-cli real (áun con el bug viejo desplegado — location
  "Chile", sin `rank_absolute` — porque el fix de Go no se ha pusheado).
- Endpoint de lectura `GET /ventas/api/aremko-cli/seo-rankings-history/?weeks=8`
  (`ventas/api_aremko_cli.py`, función `seo_rankings_history`), público sin
  auth, mismo criterio que `seo-snapshots`. Probado end-to-end en local: 200,
  agrupado por keyword, más antiguo primero.
- Endpoint cron `POST /ventas/api/cron/sync-seo-rankings/` (X-API-KEY) para
  disparar el sync semanalmente — **pendiente que Jorge configure el job en
  cron-job.org** (mismo día que `snapshot-weekly-traffic`, antes de que el
  loop despierte los lunes). Sin ese cron, el historial no se llena solo.
- **Pendiente: Jorge debe confirmar el push de este repo a `main`** (incluye
  migración nueva — Render no corre `migrate` automático, hay que correrlo a
  mano desde el Shell de Render tras el deploy, igual que siempre).

_Impacto en comparabilidad: cualquier rank-check de DataForSEO ANTES de que
el fix de Go esté deployado sigue siendo "Chile" a nivel país + cálculo con
el bug — no comparable 1:1 con los ciclos posteriores al deploy._

**Cierre 2026-07-06 (mismo día): fix deployado y verificado en producción.**
`aremko-cli` (commit `a0a999e`) y `booking-system-aremko` (commit `c1c30b8`)
pusheados a `main`; migración `aremko_cli_sync` aplicada a mano por Jorge en
el Shell de Render (auto-migrate off, como siempre). Primer sync real
corrido en prod (`python manage.py sync_aremko_cli_seo_rankings`) — este es
el **baseline correcto** (location `"Puerto Varas,Los Lagos,Chile"`,
posición orgánica real) contra el que comparar de aquí en adelante:

| Keyword | Posición orgánica | rank_absolute | URL |
|---|---:|---:|---|
| `aremko` (marca) | **1** ✅ | 2 | `/` |
| `tinajas puerto varas` | **1** ✅ | 1 | `/tinas/` |
| `cabaña con tina caliente puerto varas` | **1** ✅ | 2 | `/tinas/` |
| `masajes puerto varas` | 3 | 6 | `/masajes/` |
| `spa puerto varas` | 7 | 12 | `/` |
| `termas en puerto varas` | 9 | 13 | `/` (post nuevo aún no rankea) |
| `termas puerto varas` | 11 | 16 | `/` (post nuevo aún no rankea) |
| `escapada romántica puerto varas` | 17 | 21 | `/alojamientos/` |

Nota: `termas puerto varas`/`termas en puerto varas` siguen resolviendo a la
home, no al post `/blog/termas-puerto-varas/` publicado el 2026-07-02 —
esperable, Google todavía no lo indexó/rankeó para esa keyword específica
(5 días). Revisar en el próximo ciclo si el post empieza a aparecer.

**Pendiente de Jorge:** configurar el cron job semanal en cron-job.org
(`POST /ventas/api/cron/sync-seo-rankings/`, header `X-API-KEY`) para que el
historial se siga llenando solo — sin eso, la única fila que hay es esta del
2026-07-06, corrida a mano.

_(Actualización 2026-07-06: Jorge configuró el cron en cron-job.org, probado
200 OK. Se sigue llenando solo desde entonces.)_

---

### Ciclo 2 — 2026-07-14 (segunda corrida del loop)

**Snapshot GA4 (historial real, últimas 4 semanas — sesiones TOTALES, todos los canales):**

| Semana | Sesiones | Conv | Engagement | Dur.media | WhatsApp clk |
|--------|---------:|-----:|-----------:|----------:|-------------:|
| 06-22  | 1079 | 53 | 52% | 185s | 52 |
| 06-29  | 805  | 72 | 61% | 237s | 69 |
| 07-06  | 896  | 87 | 65% | 192s | 85 |
| **07-13** | **1099** | **121** | **54%** | **200s** | **120** |

- Semana 07-13 = **la mejor de la serie en conversiones (121, máx.)** y WhatsApp
  clicks (120, máx.), con sesiones al alza (896→1099, +23%). El engagement bajó
  de 65% a 54% — típico de un mix con algo más de tráfico de campaña/pago que
  diluye el % aunque suba el volumen absoluto de conversiones. Señal de salud:
  buena, tráfico creciendo y convirtiendo.

**Snapshot GSC (2 semanas completas comparables — dato confiable desde 07-02):**

| Semana | Clicks | Impresiones | CTR | Pos media |
|--------|-------:|------------:|-----:|----------:|
| 07-06  | 195 | 2530 | 7.71% | 5.96 |
| **07-13** | **322** | **2876** | **11.2%** | **6.07** |

- **Mejor semana de clicks y CTR de toda la serie** (+65% clicks vs semana
  previa, +14% impresiones). Posición media estable ~6. El crecimiento es real,
  no un hueco de permiso.

**Keywords protegidas — GSC (semana 07-13) + rank-check DataForSEO (foto Puerto Varas) + tendencia persistida (07-07→07-13):**

| Keyword | GSC pos (clk/imp) | DataForSEO pos | Tendencia rank |
|---|---|---:|---|
| `aremko` (marca) | 1.44 (82/178) | **1** | 1→1 ✅ |
| `aremko spa` | 1.0 (29/62) | — | domina ✅ |
| `tinajas puerto varas` (con J) | 1.66 (7/90) | **1** | 1→1 ✅ (GSC mejoró 2.86→1.66) |
| `cabaña con tina caliente puerto varas` | — | **1** | 1→1 ✅ |
| `masajes puerto varas` | 2.93 (12/90) | 3 | 3→3 ✅ (imp casi ×2: 42→90) |
| `spa cerca de puerto varas` | — | 3 | nuevo tracking ✅ (→/masajes/) |
| `spa puerto varas` | fuera del top GSC | 7 | 7→7→7→7 ⚠️ **ESTANCADA 3 sem** |
| `termas puerto varas` | 3.84 (5/111) | 9 (oscila, hoy fuera top10) | 11→9 (mejora lenta, cluster duro) |
| `termas en puerto varas` | 8.92 (2/106) | 9 | 9→8 |
| `escapada romántica puerto varas` | — | 16 | 17→16→16→14 (sube lento, pág.2) |

- **Marca + tinajas + cabaña-con-tina + masajes: sólidas en top 3.** ✅
- **`spa puerto varas` es la única keyword protegida no-romance estancada: pos 7
  tres semanas seguidas** (DataForSEO), bloqueada por hoteles (wyndhampettra,
  dreams, hotelbellavista, cabañadellago) + Instagram. En GSC ni aparece la
  cabeza exacta entre las top queries — solo branded + masajes.

**Queries nuevas/notables sin contenido dedicado o mal capturadas:**

1. **`termas cerca de puerto montt` — NUEVA esta semana:** pos 5.85, 4 clk /
   27 imp, **CTR 14.8%**. Demanda geo de termas desde Puerto Montt. El post de
   Pto Montt en la cola de blog es de MASAJES (`masajes-cerca-de-puerto-montt`),
   no cubre termas/tinas.
2. **`termas en puerto varas` — 106 imp** (la query no-marca de termas más
   grande), pero pos 8.92 / CTR 1.89%. El post `/blog/termas-puerto-varas/` ya
   quedó **indexado** (261 imp) pero rankea pos **9.45 con CTR 0.38%** — no
   captura los clicks todavía; además compite con el home (pos ~3.84 en GSC) por
   la misma intención (posible canibalización).
3. **Cluster `cabañas con tinaja(s) puerto varas` creciendo:** `cabañas con
   tinajas puerto varas` pos 9.11 (27 imp, era 8.54) + `cabañas con tinaja en
   puerto varas` pos 10.27 (15 imp). Aremko gana el SINGULAR "cabaña con tina
   caliente" (DataForSEO pos 1) pero las variantes plurales con grafía "tinaja(s)"
   caen a página 1-bottom/2. `/alojamientos/` tiene 533 imp/sem (pos 7.21) con
   meta genérica sin la grafía "tinaja".

**Reservas de la semana (contexto, 07-06..07-13):** 54 reservas / **$6.42M**.
Combo estrella cabaña+tina+masaje (3-en-1): 12 reservas / $2.93M. La demanda
orgánica sí está traduciendo a negocio. ✅

**Estado de la cola de blog (loop de publicación 2026-07-12):** ya se publicaron
`ritual-del-rio` + `pausa-junto-al-rio` (2 de 4 programas); `refugio` + `noche`
pendientes. El único post del cluster SPA (`que-es-spa-boutique-aremko`,
keyword `spa boutique puerto varas`) está en la **posición 15/18** de la cola →
a 1/semana no se publica hasta **~octubre**.

---

#### Recomendaciones NUEVAS (Nivel 2 — SOLO PROPUESTA, aplica Jorge)

**REC 1 — `spa puerto varas` estancada 3 semanas: adelantar el post de SPA en la cola y apuntarlo también al head term.**
Es la única keyword protegida no-romance sin mover (pos 7), el cluster SPA no
tiene NINGUNA URL viva, y el único post SPA de la cola no sale hasta ~octubre.
Palancas concretas (código + admin, las aplica Jorge):

- **Reordenar `PRIORITY_ORDER`** en
  `aremko_blog/management/commands/publish_next_blog_draft.py`: mover
  `que-es-spa-boutique-aremko` de la posición 15 a la **posición 5** (justo
  después de los 4 programas), para que la cola lo publique en ~3 semanas y no
  en octubre. Es 1 línea; la propongo como texto, no la edito.
- Al publicarlo, **ampliar su `keyword_root`** de `spa boutique puerto varas`
  (long-tail) a cubrir también `spa puerto varas` (head): agregar un H2 tipo
  *"Spa en Puerto Varas: qué esperar"* e **enlaces internos** desde `/masajes/`
  y el footer del home con ancla exacta **"spa en Puerto Varas"** → el post.
- Señal a favor: `/masajes/` ya rankea **#3 en "spa cerca de puerto varas"**
  (DataForSEO) — Google ya asocia Aremko con "spa", falta empujar la cabeza
  exacta. Nota realista: es un head term con hoteles + IG arriba; un post + link
  interno es un empujón, no garantía de top 3 — medir en 2-3 ciclos.

**REC 2 — Ampliar el post de termas (ya indexado) para capturar `termas cerca de puerto montt` y consolidar el cluster.**
El post `/blog/termas-puerto-varas/` ya rankea (261 imp) pero pos 9.45 / CTR
0.38%. En vez de crear contenido nuevo, **sumarle una sección** que ataque la
query geo nueva con la URL que YA existe (`BlogPost` → `body_md` + FAQ):

- H2 nuevo: **"¿Termas cerca de Puerto Montt?"**
  Cuerpo propuesto (misma voz honesta del post): *"Si buscás termas cerca de
  Puerto Montt, la respuesta honesta es la misma que en Puerto Varas: no hay
  termas naturales a la vuelta de la esquina. Pero Aremko queda a solo 20
  minutos de Puerto Montt por la ruta 5 — tinas artesanales de agua caliente a
  38-39° junto al río Pescado, abiertas hasta medianoche. Para muchos desde
  Puerto Montt es el plan de tarde más cercano que de verdad se siente como unas
  termas (y con garantía: a 37° o menos, la tina es gratis)."*
- Item FAQ nuevo (para el schema JSON-LD del post): *P: "¿Hay termas cerca de
  Puerto Montt?" — R: "No hay termas naturales inmediatas a Puerto Montt; las
  más cercanas quedan a 1½–2 h. La alternativa más cercana son las tinas de agua
  caliente de Aremko en Puerto Varas, a 20 min por la ruta 5."*
- **Consolidar canibalización:** hoy el home (pos ~3.84) y el post (pos 9.45)
  compiten por "termas puerto varas". Enlazar internamente desde las menciones
  de "termas" del home hacia el post, para concentrar la señal en una sola URL.

**REC 3 — Reescribir el meta_description de Alojamientos (`SEOContent` → Alojamientos) para el cluster "cabañas con tinaja(s)".**
Query plural creciendo (pos 9-11, ~42 imp/sem) que Aremko no captura pese a
ganar el singular. La meta actual no trae la grafía "tinaja" (con J) que la
gente busca:

- **Actual (147):** "Cabañas privadas con tina caliente y vista al lago en
  Puerto Varas. Escapada romántica perfecta con spa, desayuno y servicios
  premium. ¡Reserva ahora!"
- **Propuesta (153/160):** **"Cabañas con tina caliente (tinaja) en Puerto
  Varas, junto al río Pescado. Alojamiento privado con spa, desayuno y tinas
  hasta medianoche. Reserva online."**
  (Incorpora la grafía "tinaja", "junto al río Pescado" y "hasta medianoche" —
  diferenciadores reales — sin perder "cabañas con tina caliente".)

_Estado (actualizado en Ciclo 3, 2026-07-20, verificado live):_
- ✅ **REC 2 APLICADA** — el post `/blog/termas-puerto-varas/` ya menciona
  "Puerto Montt" (4 ocurrencias en el HTML live). Baseline a batir para
  `termas cerca de puerto montt`: pos 5.85, 4 clk / 27 imp, CTR 14.8% (07-13).
- ✅ **REC 3 APLICADA** — el `meta_description` de `/alojamientos/` es
  exactamente el texto propuesto ("Cabañas con tina caliente (tinaja) en
  Puerto Varas, junto al río Pescado. Alojamiento privado con spa, desayuno y
  tinas hasta medianoche. Reserva online."). Verificado live.
- ⏳ **REC 1 PENDIENTE** — el post SPA sigue sin publicarse
  (`/blog/que-es-spa-boutique-aremko/` → 404) y `spa puerto varas` sigue
  estancada (ver Ciclo 3, se retoma con dato nuevo).

---

### Ciclo 3 — 2026-07-20 (tercera corrida del loop)

**Titular del ciclo:** la foto de GSC muestra clics a la baja (−27% s/s), pero
**la caída es casi 100% de MARCA** — el orgánico no-marca se mantiene sano. Dos
señales nuevas positivas: demanda en inglés ("hot tub puerto varas") y
`masajes puerto varas` apareciendo en **#1 orgánico** en la foto de DataForSEO.

**Snapshot GA4 (historial real, últimas 4 semanas — sesiones TOTALES, todos los canales):**

| Semana | Sesiones | Conv | Engagement | Dur.media | WhatsApp clk | Reservas GA4 |
|--------|---------:|-----:|-----------:|----------:|-------------:|-------------:|
| 06-29  | 805  | 72  | 61% | 237s | 69  | 243 |
| 07-06  | 896  | 87  | 65% | 192s | 85  | 64  |
| 07-13  | 1099 | 121 | 54% | 200s | 120 | 89  |
| **07-20** | **1422** | **167** | **56%** | **178s** | **167** | **139** |

- Semana 07-20 = **máximo de la serie en sesiones (1422), conversiones (167) y
  WhatsApp clicks (167)**. Tráfico creciendo y convirtiendo. Salud GA4:
  excelente. (`reservation_completed` de GA4 sigue ~0 — esperable: la reserva
  se cierra por WhatsApp/Flow fuera del funnel GA4, no es una caída real.)

**Snapshot GSC (semanas comparables, dato confiable desde 07-02):**

| Semana | Clicks | Impresiones | CTR | Pos media |
|--------|-------:|------------:|-----:|----------:|
| 07-02 (parcial, jueves de alta) | 242 | 2526 | 9.58% | 6.37 |
| 07-06  | 195 | 2530 | 7.71% | 5.96 |
| 07-13  | 322 | 2876 | 11.2% | 6.07 |
| **07-20** | **234** | **2922** | **8.01%** | **6.30** |

- **Clicks −27% s/s (322→234), pero es un blip de MARCA, no de orgánico real.**
  Desglose: clics de marca ~167→~87 (−80); clics NO-marca ~155→~147 (≈plano).
  El total cayó −88 y ~80 de esos 88 son marca. Impresiones incluso subieron
  (+1.6%). El orgánico de trabajo (tinas/masajes/termas/spa) NO retrocedió.
- Dentro de la marca, el retroceso real a vigilar: **`aremko spa` cayó de
  pos 1.0 (07-13) a pos 4.12 (07-20)** en GSC, y `aremko` bajó CTR 46%→20%
  con menos impresiones de marca (178→148). Probable ruido de SERP de marca /
  menor volumen de búsqueda esa semana; no hay pérdida de contenido detrás.
  A confirmar el próximo lunes si `aremko spa` vuelve a pos 1.

**Keywords protegidas — GSC (07-20) + rank-check DataForSEO (foto viva) + tendencia persistida (07-07→07-20):**

| Keyword | GSC pos (clk/imp) | DataForSEO foto | Tendencia persistida | Estado |
|---|---|---|---|---|
| `aremko` (marca) | 1.22 (30/148) | **1** | 1→1→1→1→1 | ✅ sólida (menos clics, ver arriba) |
| `aremko spa` | 4.12 (10/72) | — | — | ⚠️ **cayó de 1.0 a 4.12 en GSC — vigilar** |
| `tinajas puerto varas` (con J) | 1.89 (6/89) | **1** | 1→1→1→1→1 | ✅ sólida |
| `cabaña con tina caliente puerto varas` | 11.13 (variante "tinaja", 1/31) | **1** | — | ✅ #1 (singular) |
| `masajes puerto varas` | 2.57 (8/65) | **1** ↑ (persistido 3) | 3→3→3→3→3 | ✅ **posible salto a #1 (foto viva), a confirmar** |
| `spa cerca de puerto varas` | — | 3 | — | ✅ estable (→/masajes/) |
| `spa puerto varas` | **7.20 (6/69), CTR 8.7%** ← NUEVO en GSC | 8 | 7→7→7→7→7 | ⚠️ **estancada pos 7-8, 4+ semanas** |
| `termas puerto varas` | 4.90 (4/71) | 10 | 11→11→9→9→10 | oscila 9-11 (cluster duro) |
| `termas en puerto varas` | 8.04 (5/71) | 6 ↑ | 9→8→7→8→10 | oscila 6-10 (mejora foto) |
| `escapada romántica puerto varas` | — | fuera de rango (foto) | 17→16→16→14→16 | ⚠️ oscila 14-17, borde pág.2 |

- **Marca + tinajas + cabaña-con-tina: sólidas top-1.** ✅
- **`masajes puerto varas`: la foto viva de DataForSEO lo pone en #1 orgánico
  (competitors_above vacío), aunque el sync persistido de las 09:10 registró 3.**
  Volatilidad intradía o mejora muy reciente — al menos estable en 3, con
  chance de #1. GSC lo confirma fuerte (pos 2.57). Sea 1 o 3, es la keyword
  no-marca más sana. ✅
- **`spa puerto varas` sigue estancada (pos 7-8, 4+ semanas)** bloqueada por
  hoteles (wyndhampettra, dreams, hotelbellavista, cabañadellago) + Instagram +
  ahora tripadvisor.cl. **Dato NUEVO: por primera vez aparece en las top queries
  de GSC con clics reales (6 clk / 69 imp, CTR 8.7%, pos 7.2)** — la cabeza
  exacta YA tiene demanda medible; falta subir de la pos 7. La URL que rankea
  es la HOME (`/`), no un post.

**Queries nuevas/notables sin contenido dedicado o mal capturadas:**

1. **`hot tub puerto varas` — NUEVA (inglés):** pos 9.06, 16 imp, 1 clk (07-20);
   histórico `hot tub chile` pos 1. Hay demanda de turistas extranjeros con la
   grafía inglesa. `/tinas/` rankea pos 9 pero su `meta_description` NO contiene
   "hot tub" (dice "agua termal", que además choca con el mensaje honesto de "no
   hay termas naturales"). Oportunidad limpia y de bajo riesgo.
2. **`termas` (genérica, sin geo) creciendo:** 38 imp, pos 7.71, 4 clk. Y el
   SERP de `termas puerto varas` se puso MÁS competitivo: **puertovaras.org
   entró #1** + directorios/tours nuevos arriba de Aremko (nomades.com,
   turistour.cl, cordillera.travel). El cluster termas es cada vez más de
   directorios; el post ya está, toca esperar indexación/autoridad.
3. **`escapada romántica puerto varas`:** oscila 14-17 y hoy salió del rango en
   la foto. El único contenido de romance (`/blog/escapada-romantica-sur-de-
   chile/`) apunta a "sur de Chile", NO a "puerto varas" — la query con volumen
   no está en su `title`/`keyword_root`. SERP dominado por OTAs (booking,
   despegar, tripadvisor, wyndham).
4. **Micro-cluster "piscina temperada":** `piscina temperada puerto montt`
   (pos 6.5), `piscina puerto varas` (pos 3.38). Volumen bajo, no accionable aún.

**Reservas de la semana (contexto, 07-13..07-20):** **71 reservas / $7.35M**
(vs 54 / $6.42M el ciclo anterior). Combos: tina+masaje 19 res / $2.38M; solo
tinas 32 / $2.19M; 3-en-1 (cabaña+tina+masaje) 6 / $1.39M. La demanda orgánica
sigue traduciendo a negocio real, al alza. ✅

---

#### Recomendaciones NUEVAS (Nivel 2 — SOLO PROPUESTA, aplica Jorge)

**REC 1 — Capturar la demanda en inglés "hot tub" en la meta de Tinas (`SEOContent` → Tinas), protegiendo el #1 de "tinajas puerto varas".**
Señal nueva de este ciclo (`hot tub puerto varas` pos 9.06, 16 imp; histórico
`hot tub chile` pos 1). De paso corrige la meta actual, que tiene doble espacio
y dice "agua termal" (impreciso: las tinas se calientan por aerotermia + solar,
no son termas naturales — choca con el mensaje honesto del post de termas).

- **Actual (139):** "Relájate en nuestras tinas calientes al aire libre  en
  Puerto Varas. Sesiones privadas, agua termal y ambiente romántico. ¡Reserva
  online!"
- **Propuesta `meta_description` (157/160):** **"Tinas y tinajas calientes (hot
  tub) en Puerto Varas, junto al río Pescado, a 38-39°. Sesiones privadas,
  aerotermia + solar, hasta medianoche. Reserva online."**
  (Mantiene "tinas" + "tinajas" que ya rankean #1, agrega "hot tub", suma los
  diferenciadores reales 38-39°/aerotermia+solar/medianoche, quita el doble
  espacio y el impreciso "agua termal". El `meta_title` / H1 de la categoría
  NO se toca — ahí vive la fuerza del #1 en "tinajas puerto varas".)

**REC 2 — Re-apuntar el post de romance existente a "escapada romántica puerto varas" (`BlogPost` → `escapada-romantica-sur-de-chile`).**
La query con volumen es "…puerto varas" (oscila 14-17, hoy fuera de rango), pero
el post apunta a "sur de Chile" en su `title` y `keyword_root`. No crear nada
nuevo: reorientar geográficamente el que ya existe (sin cambiar el slug, para no
romper la URL — solo campos de contenido/meta):

- `keyword_root`: de `escapada romántica sur de chile` → **`escapada romántica puerto varas`**
- `meta_title` propuesto (63): **Escapada romántica en Puerto Varas: 2 días junto al río | Aremko**
- `meta_description` propuesta (155/160): **Escapada romántica en Puerto Varas:
  pack cabaña + tina caliente + masaje desde $190.000, junto al río Pescado, a
  20 min del centro. Reserva tu fin de semana.**
  (Reusa el precio $190.000 que ya está publicado — no cambiar precios acá.)
- Agregar (si no está) un H2 con la frase exacta: **"Escapada romántica en
  Puerto Varas: qué incluye"**.
- Nota realista: el SERP de romance está dominado por OTAs (booking, despegar,
  tripadvisor, wyndham) — reorientar la keyword es correcto pero es un empujón,
  no garantía de top 10. Medir en 2-3 ciclos si sube del rango 14-17.

**REC 3 — `spa puerto varas` (pendiente de Ciclo 2, con DATO NUEVO que la vuelve prioritaria): publicar el post SPA esta semana + concentrar la señal "spa" en la HOME (la URL que rankea).**
No es repetir la REC 1 del Ciclo 2 tal cual: ahora hay evidencia de que la
cabeza exacta YA convierte impresiones en clics (6 clk / CTR 8.7% en GSC, primera
vez), y sabemos que la URL que rankea la cabeza es la **HOME** (`/`), no un post.
Dos palancas concretas, ambas de bajo riesgo:

- **(a) Adelantar la publicación del post SPA** (`que-es-spa-boutique-aremko`,
  hoy 404 / borrador) — mover su slug a la posición ~5 de `PRIORITY_ORDER` en
  `aremko_blog/management/commands/publish_next_blog_draft.py` para que salga en
  la próxima corrida del loop de publicación, no en octubre. (1 línea; la
  propongo como texto, no la edito.)
- **(b) Enlace interno con ancla exacta "spa en Puerto Varas" desde `/masajes/`
  (que ya rankea #1 en "masajes" y #3 en "spa cerca de puerto varas") hacia la
  HOME `/`.** A diferencia del Ciclo 2 (que enlazaba al post inexistente), este
  enlaza a la URL que HOY rankea la cabeza (pos 8), concentrando ahí la señal
  "spa" sin depender de que el post ya exista. Google ya asocia `/masajes/` con
  "spa" — este link traslada parte de esa asociación a la home.
- Realista: es un head term con hoteles + IG + tripadvisor arriba; post + link
  interno es un empujón medible en 2-3 ciclos, no un salto garantizado a top 3.

**Para vigilar (no es recomendación, es alerta):** `aremko spa` cayó de pos 1.0
a 4.12 en GSC esta semana. Es un término de marca propio — no debería estar en
pos 4. Revisar el próximo lunes: si persiste, mirar si algún agregador/OTA se
metió en el SERP de marca o si Google cambió el panel. Si vuelve a pos 1, era
ruido de la semana.

_Estado: propuestas dejadas por el loop; pendiente revisión/aplicación de Jorge._

---

## Loop de publicación de blog (nuevo 2026-07-12)

Distinto del loop de SEO de arriba (que analiza tráfico/rankings) — este es
el mecanismo para sostener un ritmo de publicación del blog sin que dependa
de que alguien se siente a escribir cada semana.

**Cómo funciona:** en sesión interactiva (2026-07-12) se redactaron y
revisaron con Jorge **16 posts nuevos** — origen: gap analysis del catálogo
real (programas sin blog dedicado, tipos de masaje del catálogo, keywords
con volumen real detectado vía DataForSEO donde Aremko no tenía contenido,
clusters SPA/BOUTIQUE vacíos) — y se sembraron como **BORRADOR**
(`is_published=False`) vía 16 management commands `seed_blog_post_*` en
`aremko_blog/management/commands/`. Cada uno idempotente por slug,
`update_or_create`, con FAQ + schema JSON-LD.

**El loop NO genera contenido nuevo.** Solo publica, uno por semana, el
siguiente borrador de una cola ya escrita y revisada:

```
python manage.py publish_next_blog_draft            # publica el siguiente
python manage.py publish_next_blog_draft --dry-run   # solo muestra cuál publicaría
```

Orden de la cola (`PRIORITY_ORDER` en
`aremko_blog/management/commands/publish_next_blog_draft.py`, acordado con
Jorge — "prioridad comercial"): 4 programas (Ritual del Río, Pausa, Refugio,
Noche de Aguas Calientes) → 3 keyword-driven (masajes cerca de mí, masajes
cerca de Puerto Montt, biopiscinas vs tinas) → 4 tipos de masaje (Tui-Na,
Tailandés, Drenaje Linfático, Deportivo vs Piedras Calientes) → 5
evergreen/soporte (Río Pescado, spa boutique, elegir programa, invierno,
pagar en cuotas).

**Disparo:** `POST /ventas/api/cron/publish-next-blog-draft/` (header
`X-API-KEY`) — **pendiente que Jorge configure el job semanal en
cron-job.org**, sugerido lunes 09:15 (después de `snapshot-weekly-traffic`
09:00 y `sync-seo-rankings` 09:10). Mientras no exista ese cron, publicar a
mano corriendo el comando en el Shell de Render, o seguir publicando
manualmente desde el admin como antes.

**Para agregar un post nuevo a la cola en el futuro:** escribir su
`seed_blog_post_*` (mismo patrón: borrador, FAQ, grounded en datos reales,
sin inventar precios/servicios), correrlo para crear el borrador, y sumar su
slug a `PRIORITY_ORDER` en el lugar que corresponda — no requiere tocar el
cron ni la lógica del comando.
