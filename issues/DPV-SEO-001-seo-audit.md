# DPV-SEO-001 · Auditoría SEO destinopuertovaras.cl

**Fecha auditoría:** 2026-04-29
**Sitio:** https://destinopuertovaras.cl (apex; www.destinopuertovaras.cl 301 → apex)
**Estado del sitio:** live desde 2026-04-27, ~46 circuitos publicados.

---

## Tabla de trabajos

| # | Trabajo | Prioridad | Estado | Notas |
|---|---------|-----------|--------|-------|
| 1 | Arreglar `sitemap.xml` (HTTP 500) | 🔴 Crítico | ✅ Completado | 54 URLs (1 home + 53 circuitos), HTTP 200, lastmod por circuito. Fix commit c59de7f |
| 2 | Agregar `Sitemap:` directive en robots.txt | 🔴 Crítico | 🔄 En progreso | Pendiente deploy + verificación |
| 3 | Agregar `<link rel="canonical">` self-referencing en template base | 🔴 Crítico | ✅ Completado | Verificado en home + circuit detail. Commit 1847b5b |
| 4 | Implementar JSON-LD estructurado | 🔴 Crítico | ✅ Completado | Validado: home (Org+WebSite) + detail (TouristTrip 5 stops + BreadcrumbList). Commits d36f9f1, 7c403bf |
| 5 | Convertir CSS `background-image` → `<img alt>` en templates listing/detail | 🟡 Importante | ✅ Completado | Verificado: cards (`alt={{ circuit.name }}`), stops (`alt={{ place.name }} – {{ location }}`), modal hero. loading=lazy. Commit 79db9f9 |
| 6 | Cambiar `og:image` default de homepage (no usar logo Aremko) | 🟡 Importante | 🔄 En progreso | Pendiente deploy + verificación |
| 7 | Configurar Google Search Console + verificar dominio + enviar sitemap | 🟡 Importante | ⏳ Pendiente | Requiere acceso del usuario; depende de #1 |
| 8 | Decidir si abrir páginas de Place a público (long-tail SEO) | 🟢 Estratégico | ⏳ Pendiente | Diseño actual: places no son URLs públicas |
| 9 | PageSpeed Insights con API key (Core Web Vitals) | 🟢 Estratégico | ⏳ Pendiente | Rate-limit sin key; obtener API key |
| 10 | Estrategia contenido editorial (blog) para keywords informacionales | 🟢 Estratégico | ⏳ Pendiente | "qué hacer en Puerto Varas", "tours sur de Chile", etc. |

---

## Leyenda de estados

- ⏳ **Pendiente** — sin empezar
- 🔄 **En progreso** — trabajo activo
- ✅ **Completado** — desplegado y verificado en prod
- ⚠️ **Parcial** — implementado parcialmente; queda algo por cerrar
- ❌ **Bloqueado** — no se puede avanzar (esperar input externo, bug upstream, etc.)

---

## Hallazgos detallados

### #1 Sitemap.xml roto
- **Issue:** `https://destinopuertovaras.cl/sitemap.xml` → HTTP 500 (Django Server Error)
- **Impacto:** Google no descubre URLs nuevas eficientemente. Search Console reportará error.
- **Fix sugerido:** Configurar `django.contrib.sitemaps` con un `Sitemap` por modelo. Registrar en `urls.py`.

### #2 Falta directiva Sitemap en robots.txt
- **Issue:** robots.txt actual solo tiene rules; no apunta al sitemap.
- **Robots.txt actual permite:** crawl general, bloquea bots de AI training (Claude, GPT, Bytespider, etc.) — decisión válida.
- **Fix:** Agregar línea `Sitemap: https://destinopuertovaras.cl/sitemap.xml`.

### #3 Sin canonical tags
- **Issue:** Ni homepage ni `/circuitos/calbuco-pedraplen-costanera/` tienen `<link rel="canonical">`.
- **Impacto:** Variantes con/sin trailing slash, con UTMs, podrían indexarse como duplicados.
- **Fix:** En template base, `<link rel="canonical" href="https://destinopuertovaras.cl{{ request.path }}">`.

### #4 Cero JSON-LD
- **Issue:** No hay `application/ld+json` en ninguna página probada.
- **Impacto:** Pierdes rich snippets en SERP (breadcrumbs, fechas, ratings).
- **Fix por tipo:**
  - Homepage: `Organization` + `WebSite` con `SearchAction`
  - Circuito: `TouristTrip` con `BreadcrumbList`
  - Place: `TouristAttraction` con `geo`, `image`

### #5 Imágenes en CSS background-image
- **Issue:** 0 `<img>` tags en pruebas; todo es `background-image: url(...)`. 10 bg-images en página Calbuco.
- **Impacto:** Google Image Search no indexa; sin alt text; sin tráfico de búsqueda visual.
- **Fix:** Templates con `<img src="..." alt="..." loading="lazy" decoding="async">`.

### #6 og:image homepage incorrecta
- **Issue:** `og:image` de la home = `aremko.cl/static/aremko_logo.png`.
- **Impacto:** Compartir DPV en redes muestra logo Aremko, no imagen del destino.
- **Fix:** Crear hero acuarela panorámica DPV; usar como og:image default.

### #7 Search Console
- **Issue:** Sin verificar / sin envío de sitemap.
- **Acción requerida:** Usuario verifica dominio (DNS TXT o HTML file) en Search Console + envía sitemap.

### #8 Páginas de Place
- **Estado actual:** Places no tienen URLs públicas (`/lugares/<slug>/` no existe). Solo aparecen como stops dentro de circuitos.
- **Tradeoff:** abrir places suma cientos de páginas long-tail (volcán-osorno, saltos-petrohue) pero diluye autoridad si las páginas son thin.
- **Decisión pendiente.**

### #9 Core Web Vitals
- **Estado:** PageSpeed Insights API rate-limited sin key.
- **Acción:** Obtener API key de Google Cloud o medir manual con Chrome DevTools / web.dev/measure.

### #10 Contenido editorial
- **Gap:** Solo páginas transaccionales (circuitos). Faltan páginas informacionales que rankean para queries top-funnel.
- **Idea:** blog con artículos tipo "Qué hacer en Puerto Varas en 3 días", "Mejor época para visitar el sur de Chile", "Comparativa Saltos del Petrohué vs Cascada Escondida".

---

## Bitácora de avances

(Cada vez que cerremos o avancemos un trabajo, anotar aquí con fecha)

- 2026-04-29 · auditoría inicial completa, tabla creada.
- 2026-04-29 · #1 ✅ resuelto. Causa raíz: `dpv_root_urls.py` reusaba sitemaps de `ventas` cuyos `reverse()` fallaban en el namespace DPV. Fix: nuevo `destino_puerto_varas/sitemaps.py` con `DPVHomeSitemap` + `CircuitSitemap`. Commit c59de7f. 54 URLs verificadas en `/sitemap.xml`.
- 2026-04-29 · #2 🔄 código listo. Hallazgo: DPV servía la robots.txt de Aremko (`Sitemap: aremko.cl/sitemap.xml` + `/ventas/...` Disallow). Fix: nuevo `templates/seo/robots_dpv.txt` apuntando a `destinopuertovaras.cl/sitemap.xml`; `dpv_root_urls.py` ahora carga ese template. Commit 82a2667 pushed; queda purgar cache Cloudflare (TTL 4h) o esperar.
- 2026-04-29 · #3 ✅ resuelto. Fix: `<link rel="canonical" href="https://destinopuertovaras.cl{{ request.path }}">` en `base.html`; `og:url` alineado al mismo formato. Commit 1847b5b. Verificado en home (`/`) y circuit detail (`/circuitos/calbuco-pedraplen-costanera/`).
- 2026-04-29 · #4 ✅ resuelto. Bloque `{% block json_ld %}` en `base.html`. Home: `Organization` + `WebSite` con `@graph`. Circuit detail: `TouristTrip` con `itinerary` + `BreadcrumbList`. **Bug encontrado y arreglado**: lat/lng salían con coma decimal (`-41,756`) por locale `es-CL`, rompiendo el JSON; fix con `{% load l10n %}` + `{% localize off %}`. Commits d36f9f1 (impl) + 7c403bf (locale fix). JSON validado con Python json.loads en prod: 2 items en @graph, TouristTrip con 5 stops, BreadcrumbList con 2 niveles.
- 2026-04-29 · #5 ✅ resuelto. `background-image` CSS → `<img alt loading=lazy decoding=async>` en `circuit_list.html` (hero del card) y `circuit_detail.html` (stop photo + modal hero). Alts descriptivos: cards usan `circuit.name`; stops usan `place.name – location_label`; modal usa `place.name`. CSS ajustado: `position: absolute + object-fit: cover` para mantener layout; regla `> *:not(img)` para que overlay y badges queden encima. Commit 79db9f9.
