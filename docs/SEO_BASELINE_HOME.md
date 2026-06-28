# SEO Baseline — Home `/` (aremko.cl)

Capturado 2026-06-28, ANTES del rediseño boutique. Es el checklist de "qué NO se puede perder"
al portar el nuevo diseño a la home real. Comparar contra esto al lanzar.

## Estado actual (lo que sirve hoy en prod)

| Elemento | Valor actual |
|---|---|
| **URL** | `https://www.aremko.cl/` (canonical = misma) — NO cambia |
| **Title** | `Aremko Spa Boutique · Aguas calientes junto al Río Pescado · Puerto Varas` |
| **Meta description** | `Aremko Spa Boutique en Puerto Varas: aguas calientes privadas junto al Río Pescado, masajes y alojamiento en bosque nativo. Reserva tu tina online.` |
| **H1 (prod)** | `2 días aquí equivalen a una semana de vacaciones` (dinámico desde `HomepageConfig.hero_title`) |
| **Kicker** | `AREMKO SPA BOUTIQUE` |
| **JSON-LD** | **2 bloques**: (1) `@graph` → `SpaOrSalon` (LocalBusiness: name, dirección Río Pescado km19/km4, geo, tel +56957902525, email ventas@aremko.cl, logo, image[]); (2) `{{ productos_jsonld }}` (Product/Offer dinámico) |
| **OpenGraph** | og:title `Aremko Spa Puerto Varas - Masajes, Tinajas y Alojamiento`, og:type website, og:locale es_CL, og:image 1200×630 |
| **Tracking** | GA4 `G-T3K4CTD3HJ` + Google Ads (AW-1015703959 / AW-1767221019 / AW-18196625156) + Meta Pixel |
| **Contenido (H2)** | filosofía "Vive la Experiencia Aremko", servicios, categorías, feature blog (`tinas-calientes-puerto-varas`), CTA — texto con keywords: masajes, tinas calientes, alojamiento, Puerto Varas, Río Pescado, bienestar |
| **Enlaces internos** | blog (list + post tinas-calientes-puerto-varas), `ritual_rio_landing`, servicios |
| **Imágenes** | 16 `<img>`, 15 con `alt` (1 sin alt) |
| **Fuente de textos** | `HomepageConfig` (singleton admin): hero_title/subtitle, filosofía, imágenes → Jorge edita en admin |
| **Peso HTML** | ~142 KB (home actual = 1.715 líneas de template) |
| **PageSpeed** | PENDIENTE — medir en pagespeed.web.dev (mobile) antes y después |

## Checklist de preservación (el nuevo diseño DEBE mantener)
1. **Misma URL `/`** y seguir **extendiendo `base_public.html`** → title/canonical/OG/GA4/Ads/Pixel se preservan solos.
2. Rehacer **solo `{% block content %}`**; conservar `{% block title %}`, `{% block meta_description %}` y `{% block structured_data %}` (los 2 JSON-LD) tal cual o mejorados.
3. **Un** `<h1>` (decidir: mantener "2 días aquí…" o usar la keyword "Aguas calientes junto al río").
4. **Mantener texto con keywords** (tinas calientes Puerto Varas, masajes, alojamiento, Río Pescado, bosque nativo) — curado, puede ir más abajo. Boutique ≠ cero texto.
5. **Conservar enlaces internos** (blog, servicios, landings).
6. **Seguir leyendo de `HomepageConfig`** (admin) para que Jorge mantenga control de textos/fotos.
7. **`alt` con keywords** en todas las fotos.
8. **`{% localize off %}`** en los números del JSON-LD (es-CL rompe el JSON si no).
9. **PSI ≥ actual** (medir antes/después).
10. **Post-lanzamiento:** monitorear GSC 2–4 semanas; si baja, **revertir el template en 1 commit** (misma URL, swap reversible).

## Keywords a PROTEGER (GSC, últimos 3 meses, capturado 2026-06-28)

**Marca (seguras — la búsqueda de marca encuentra la home igual):** aremko (690 clics), aremko spa (197), aremko aguas calientes puerto varas (181), arenko/aremco (mal escrito).

**⭐ Genéricas (NO perder el contenido que las posiciona):**
| Query | Clics | Impresiones |
|---|---|---|
| masajes puerto varas | 86 | 571 |
| tinajas puerto varas | 70 | 541 |
| spa puerto varas | 32 | 542 |
| masajes en puerto varas | 30 | 224 |
| masaje puerto varas | 28 | 123 |

→ La home rediseñada DEBE mantener texto/encabezados con: **"masajes (en) Puerto Varas", "tinajas/tinas (calientes) Puerto Varas", "spa Puerto Varas"**. Nota: la gente busca **"tinajas"** (con J) — conservar esa palabra, no solo "tinas".

## Pendiente
- **pagespeed.web.dev** (mobile) sobre la home → score + LCP/CLS para el baseline de performance (medir antes/después). API keyless sin cupo el 2026-06-28.
