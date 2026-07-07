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
# Rankings (usa la lista fija de 8 keywords por defecto — ver abajo)
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
varas`, `escapada romántica puerto varas`, `aremko`.

### Historial persistido de rank-check (nuevo 2026-07-06)

El endpoint `/rankings` de arriba solo da la foto del momento (cache 12h, se
pierde en cada redeploy de Render) — no permite ver evolución en el tiempo.
Para eso existe ahora, en este mismo repo Django, un historial persistido:

```bash
curl "https://www.aremko.cl/ventas/api/aremko-cli/seo-rankings-history/?weeks=8"
```

Devuelve `{"weeks_requested": N, "rankings": {"<keyword>": [{fetched_at,
found, position, rank_absolute, url, competitors_above}, ...], ...}}`, más
antiguo primero por keyword. Público, sin auth (mismo criterio que
`seo-snapshots`). Es SOLO LECTURA de lo que ya guardó
`sync_aremko_cli_seo_rankings` (app aislada `aremko_cli_sync`, modelo
`SEORankingSnapshot`, drift-safe respecto a `ventas`) — no genera nada nuevo.

**Este endpoint solo tiene datos si alguien corrió el sync.** Disparo:
`python manage.py sync_aremko_cli_seo_rankings` (a mano), o vía el cron
`POST /ventas/api/cron/sync-seo-rankings/` (header `X-API-KEY`) — **pendiente
que Jorge configure el job semanal en cron-job.org** apuntando a ese
endpoint (mismo día que `snapshot-weekly-traffic`, antes de que el loop
despierte los lunes). Hasta que ese cron exista, el paso 3 de este ciclo debe
seguir usando el rank-check en vivo (`/api/v1/seo/rankings`) como hoy, y
opcionalmente consultar este historial si ya hay algo guardado.

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
