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

_(vacío — la primera corrida del loop agrega la primera entrada acá)_
