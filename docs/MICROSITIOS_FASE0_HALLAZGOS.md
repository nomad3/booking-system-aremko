# Micrositios Aremko — Fase 0: Hallazgos de exploración

**Fecha:** 2026-08-20 · **Rama:** `claude/aremko-micrositios-rnr80q` · **Estado:** exploración solo lectura, sin código nuevo

Este documento es el entregable de la Fase 0 del proyecto "Micrositios Aremko"
(adaptación del Micro Site Blueprint a destino único). Inventaria qué existe
realmente en el repo, qué datos hay y cuáles faltan, y propone el plan de las
fases siguientes. Nada de lo aquí descrito modifica código ni base de datos.

---

## 1. Estructura del proyecto (lo relevante para micrositios)

| Pieza | Dónde | Estado |
|---|---|---|
| App core reservas/ventas | `ventas/` (modelos en `ventas/models.py`, 8.122 líneas) | Operativa |
| Checkout web | `ventas/views/checkout_views.py` (carrito en sesión → `PendingReservation` → webhook Flow → `VentaReserva`) | Operativa |
| Landings de experiencias | `/refugio/`, `/ritual-del-rio/` (noindex), `/pausa-junto-al-rio/`, `/noche-de-aguas-calientes/`, `/experiencia-romantica/`, `/celebraciones/` | Operativas |
| Blog SEO | `aremko_blog/` (~22 posts sembrados por comando, publicación semanal automática) | Operativo |
| Micrositio existente | `destino_puerto_varas/` → **destinopuertovaras.cl** (medio editorial del destino, dominio propio servido por el mismo Django vía `host_routing.py`) | Operativo |
| Generación estática / microsites | — | **No existe** (no hay `microsites/`, `dist/` ni build estático alguno) |
| SEO técnico | `ventas/sitemaps.py`, `templates/seo/robots.txt`, `ai.txt`, `llm.txt`, modelo `SEOContent` por categoría | Operativo |

**Precedente clave:** `destinopuertovaras.cl` demuestra que ya se operó la idea de
"sitio satélite con dominio propio", con reglas explícitas de no-canibalización
(`destino_puerto_varas/data/keywords_phase1.md`). El blueprint de micrositios debe
respetar el mismo criterio.

## 2. Modelos de datos: qué hay para el estudio de motivos

### Reservas (BD producción)
- `VentaReserva` (`ventas/models.py:1144`): `cliente`, `fecha_creacion` (auto), `fecha_reserva`, `total`, `estado_pago`, `estado_reserva`. **Sin campo de origen/canal/UTM.**
- `ReservaServicio` (`:1429`): `fecha_agendamiento` (**DateField**), `hora_inicio` (**CharField "HH:MM"**), `cantidad_personas`, `precio_unitario_venta`. → La **anticipación de reserva** se calcula como `fecha_agendamiento − fecha_creacion` de la venta; el día de semana sale de `fecha_agendamiento`.
- `Servicio` (`:463`): `tipo_servicio` (`tina/masaje/cabana/otro`), `categoria` FK. Ojo: conviven **4 taxonomías** de servicio no mapeadas entre sí (`Servicio.tipo_servicio`, `CategoriaServicio.nombre`, `PackDescuento.TIPO_SERVICIO_CHOICES`, `GiftCardExperiencia.CATEGORIA_CHOICES`).
- `Pago` (`:1305`): 23 métodos. Proxy de canal: `flow/webpay/mercadopago` ⇒ checkout web; `Pago.usuario` no nulo ⇒ registrado en admin; `booking` ⇒ OTA; existencia de `PendingReservation` ⇒ nació del checkout web.
- `ClienteTaxonomia` (`:2900`): agregado analítico ya calculado por cliente (mix tinas/masajes/cabañas, `pct_finde`, `pct_verano/otoño/invierno/primavera`, ticket promedio, bundles). **Reutilizable directamente para el estudio.**
- `ServiceHistory` (`:2854`, `managed=False`, tabla `crm_service_history`): histórico importado 2020-2024.

### Histórico local (repo)
- `data/servicios_historicos.csv`: **31.277 filas, 2020–2024** (columnas: cliente, servicio, cantidad, valor, reserva, checkin, categoria, año, hora, mail, teléfono). Distribución: Tinas ~15.700, Masajes ~9.450, Cabañas ~4.400, Ambientaciones 1.065. Formatos de fecha mixtos (ISO y dd/mm/yyyy) y **contiene PII** (nombres, emails, teléfonos) → todo análisis debe agregarse/anonimizarse antes de publicar.

### Atribución / UTM — el gap central
- **El checkout NO captura ni persiste UTM.** Ni `VentaReserva`, ni `Cliente`, ni `Pago`, ni `PendingReservation` tienen campos de origen.
- El **único** modelo con UTM persistente es `RefugioLead` (`:7729`): `utm_source/medium/campaign/content/term` + `referer` + sesión (`request.session['refugio_utm']`, `public_views.py:855`). Es el patrón a replicar.
- Atribución declarada: `EncuestaSatisfaccion.como_se_entero` (`instagram/facebook/google/blog/publicidad/...`).
- GA4 registra `whatsapp_click` global (`ventas/static/ventas/js/aremko-events.js` auto-trackea todo `wa.me/`), pero eso vive en GA4, no en la BD.

**Consecuencia para el blueprint:** hoy no se puede atar una reserva del carrito a
una campaña/micrositio. Para la Fase 3 hará falta persistir UTM en el checkout
(cambio de modelo + migración → **requiere aprobación explícita antes de tocar nada**).

## 3. Datos de Ads: qué hay y qué falta

- **`data/ads/` NO existe.** No hay ningún export CSV de Google Ads ni de Meta Ads en el repo (el `.gitignore` de `data/` solo permite `servicios_historicos.csv`).
- Los datos de Ads se consultan **por API en runtime**:
  - `ventas/services/google_ads_reporter.py`: cliente REST Google Ads API (cuenta `539-975-0827`), cubre campañas, ad groups, **Search Terms Report**, keywords + Quality Score. Requiere env vars `GOOGLE_ADS_*` en Render (al 2026-05-30 las credenciales OAuth estaban pendientes; verificar estado actual).
  - `ventas/services/meta_reporter.py`: Meta Graph API, cuentas publicitarias `act_455070225054110` (CLP) y `act_43311853` (USD); snapshots persistidos en `MetaSnapshot`.
- Campañas ya montadas o especificadas: **Refugio** (Meta + Google, landing `/refugio/` con leads UTM) y **Ritual del Río** (brief `docs/BRIEF_H-036_google_ads_ritual.md`, con temas de keywords y negativas ya definidos).
- Historia real de leads: `docs/INFORME_LEADS_REFUGIO_CAMPANAS.md` (discrepancia Meta 14 vs BD 3; CPL real desconocido) — lección directa para el tablero de la Fase 3: **el lead que cuenta es el de la BD/WhatsApp, no el atribuido por Meta**.
- **Este contenedor no tiene `DATABASE_URL` ni credenciales de Ads**: los scripts de Fase 1 se escriben aquí, pero se ejecutan en Render (shell o cron) o contra un export manual.

## 4. Assets reutilizables para los micrositios

- **Paleta boutique canónica** (`ventas/templates/ventas/homepage_boutique.html:218`): `--green #0f6e56`, `--rust #a85a32`, cremas `#f3ede3/#fffdf9`, dorado `#c8902a`, línea `#e8ddca`; tipografía de marca **Cormorant Garamond**. (Ignorar `modern.css`, es legado.)
- **Fotos**: repo solo trae el set real de `ventas/static/ventas/empresas_presentacion/` (tinas, cabañas, masajes). El resto vive en **Cloudinary `dtuncr1pi`** con `f_auto,q_auto` (WebP automático) — carpetas `servicios/`, `ritual_rio/`, `giftcards/experiencias/`. El logo **no está en el repo**.
- **Copy y posicionamiento listos**: `docs/MARKETING_PLAYBOOK.md` v2.0 (experiencias con nombre y precios actualizados, personas, frases ancla, diferenciales, convenciones UTM), `populate_seo_content.py` (copy SEO por categoría con FAQs), landings existentes.
- **Keyword research previo**: `ventas/data/aremko_keywords_phase1.md` (40 keywords curadas; insight: **"jacuzzi" rinde ~5x más que "tina caliente"/"hot tub"** en Suggest; "tinaja" como sinónimo regional) + 45 keywords DPV con regla anti-canibalización.
- **NAP real** (para LocalBusiness schema): Río Pescado, Camino a Ensenada km 19, Puerto Varas · `-41.277611, -72.768611` · WhatsApp `+56 9 5790 2525` · GBP "Aremko Aguas Calientes Puerto Varas" · reviews `https://g.page/r/CbKKwbV5UmD_EBM/review`.
- **Tracking existente**: GA4 `G-T3K4CTD3HJ`, gtag Ads `AW-1015703959` / `AW-1767221019` (masajes) / `AW-18196625156` (Refugio), Meta Pixel `478226496113915`, Pixel+CAPI con dedupe por `event_id`.

## 5. Datos que existen vs. datos que faltan

| Dato | ¿Existe? | Fuente / cómo obtenerlo |
|---|---|---|
| Reservas por servicio/mes/día 2020-2024 | ✅ | `data/servicios_historicos.csv` (local, analizable ya) |
| Reservas vivas + anticipación de compra | ✅ en prod | `VentaReserva.fecha_creacion` vs `ReservaServicio.fecha_agendamiento` — correr script en Render |
| Estacionalidad y mix por cliente | ✅ en prod | `ClienteTaxonomia` (pre-calculado) |
| Términos de búsqueda Google Ads | ⚠️ vía API | `google_ads_reporter.get_search_terms...` — **verificar credenciales en Render**, o export manual desde la UI de Google Ads |
| Rendimiento Meta por campaña | ⚠️ vía API | `meta_reporter` / snapshots `MetaSnapshot`, o export manual |
| UTM → reserva del carrito | ❌ | No se persiste. Gap a resolver en Fase 3 (requiere migración, pedir aprobación) |
| UTM → lead | ✅ solo Refugio | `RefugioLead` |
| Atribución declarada post-visita | ✅ en prod | `EncuestaSatisfaccion.como_se_entero` |
| Volumen de búsqueda estimado por keyword | ⚠️ parcial | Suggest-based (`aremko_keywords_phase1.md`); sin datos de volumen absoluto (Keyword Planner no está integrado) |
| Sesiones / clics WhatsApp por landing | ✅ en GA4 | `whatsapp_click` auto-trackeado; no en BD |

## 6. Riesgos y decisiones de diseño detectadas

1. **Canibalización con el sitio madre**: aremko.cl ya apunta a "tinas puerto varas", "masajes puerto varas" (landings `/tinas/`, `/masajes/`, blog activo). Un EMD `masajespuertovaras.cl` compite contra nuestra propia landing. Los micrositios deben priorizar **intenciones que el sitio madre no cubre bien** (ej. celebraciones/despedidas, jacuzzi/tinaja como término, escapada romántica genérica sin marca, alojamiento en ruta a Ensenada, inglés/portugués) o asumir el trade-off explícitamente.
2. **"Jacuzzi" > "tina caliente"** en demanda de búsqueda: los EMD candidatos deben evaluarse también en la variante jacuzzi/tinaja, no solo "tinas".
3. **PII en el CSV histórico**: cualquier artefacto de análisis que se versione debe ser agregado (sin nombres/teléfonos/emails).
4. **Lección Refugio**: la métrica de corte de la Fase 3 debe basarse en conversaciones WhatsApp reales + leads en BD, nunca en leads atribuidos por la plataforma de Ads.
5. **Sin credenciales en este entorno**: los management commands de análisis se entregan como código y se ejecutan en Render.

## 7. Plan propuesto (siguientes fases)

### Fase 1 — Estudio de motivos (`analysis/` + `docs/estudio-motivos.md`)
1. **Análisis local inmediato** del CSV histórico: reservas por categoría/servicio/mes (estacionalidad 2020-2024), ticket por categoría, día de semana. Script en `analysis/`, salida agregada y anónima.
2. **Management command solo lectura** (`analysis/` o `ventas/management/commands/`, a definir) para correr en Render: agregados de `VentaReserva`/`ReservaServicio` (por tipo_servicio, mes, día, anticipación de reserva, proxy de canal vía método de pago), `ClienteTaxonomia`, `EncuestaSatisfaccion.como_se_entero` y `RefugioLead` por utm. Salida JSON/CSV agregada, sin PII.
3. **Datos de Ads**: (a) si las credenciales `GOOGLE_ADS_*` están activas en Render → command que exporte Search Terms Report de los últimos 12 meses a CSV agregado; (b) si no → pedir export manual (Google Ads UI: Informes → Términos de búsqueda; Meta: rendimiento por campaña/conjunto). **Necesito confirmación de cuál camino.**
4. Clasificación de términos en motivos (romántico/aniversario, tinajas-jacuzzi, masaje, alojamiento en ruta, regalo, celebración/grupo, extranjero) y tabla de priorización → recomendación de los 2 micrositios warm-up.

### Fase 2 — Generación (`microsites/`)
- App/carpeta `microsites/` con configs YAML por sitio (dominio, keyword, textos, CTA WhatsApp con texto pre-llenado único, UTM) + command `build_microsites` que renderiza templates Django a HTML/CSS estático en `dist/<dominio>/` (sitemap.xml, robots.txt, OG, LocalBusiness/Spa + FAQPage schema con NAP real, imágenes Cloudinary `f_webp`).
- Verificación de disponibilidad de EMDs en NIC Chile antes de proponer la lista final; **la compra de dominios la decides tú**.

### Fase 3 — Medición
- Tablero mínimo: conversaciones WhatsApp por texto pre-llenado + Cloudflare Web Analytics (sin cookies) + reservas por UTM en el carrito.
- Prerrequisito: persistir UTM en checkout (`PendingReservation`/`VentaReserva`), replicando el patrón `RefugioLead`. **Cambio de modelo + migración → se propone y se aprueba antes de implementar.**

### Preguntas abiertas (bloquean Fase 1 parcial o totalmente)
1. ¿Las credenciales de Google Ads API ya están cargadas en Render, o prefieres pasarme exports manuales (Search Terms 12m + Meta por campaña)?
2. ¿Corro los agregados de reservas vía shell de Render, o prefieres otro mecanismo?
3. ¿De acuerdo con priorizar sub-nichos que NO canibalicen `/tinas/` y `/masajes/` del sitio madre?
