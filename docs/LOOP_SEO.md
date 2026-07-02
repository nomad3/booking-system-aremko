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

## Qué hacer en cada ciclo

1. Leer la última entrada de este archivo (qué se propuso, si Jorge respondió algo).
2. Traer los últimos 8 snapshots semanales (GA4 + GSC ya guardados, no generar nada nuevo):

   ```
   curl "https://www.aremko.cl/ventas/api/aremko-cli/seo-snapshots/?weeks=8"
   ```

   Sin auth, sin token. Aplicar la regla de arriba sobre semanas GSC en cero.

3. Opcional, para ver si el tráfico orgánico se traduce en negocio real (mismo
   criterio "no confiar solo en la plataforma" que los loops de ads, aunque acá
   el vínculo es más indirecto que en ads):

   ```
   curl "https://www.aremko.cl/ventas/api/aremko-cli/bookings/family-combinations-range/?date_start=<inicio semana>&date_stop=<fin semana>"
   ```

4. Comparar contra la última entrada de la bitácora: ¿subió/bajó el tráfico
   orgánico?, ¿alguna keyword protegida perdió posición?, ¿algún `top_query`
   nuevo con volumen que no tiene contenido dedicado?
5. Producir 1-3 recomendaciones NUEVAS y concretas — preferí propuestas
   REDACTADAS (el meta_description exacto, el título del post, el outline)
   sobre sugerencias vagas tipo "mejorar el SEO de X".
6. Agregar una entrada nueva al FINAL de este archivo con: fecha, snapshot
   corto (tráfico GA4 + GSC de la semana, keywords protegidas), y las
   recomendaciones redactadas. Commitear (solo este .md) con mensaje en español.
7. Nivel 2 — SOLO PROPONER: no editar modelos de Django, no publicar nada. Solo
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
- ⏳ REC 1 (post termas): pendiente, en cola en esta misma sesión.
