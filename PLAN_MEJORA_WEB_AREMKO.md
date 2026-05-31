# Plan de Mejora Web — Aremko Spa (aremko.cl)

> **Documento vivo.** Se actualiza cada vez que se completa o se aprueba una etapa.
> Última actualización: **2026-05-30** · Responsable técnico: Claude Code · Owner: Jorge Aguilera

## 🎯 Objetivo
Resolver las dos críticas recibidas en las encuestas de satisfacción de clientes:
1. **Calidad visual** — "la página no refleja lo lindo del lugar".
2. **Proceso de compra** — alto abandono del carrito; "no es lo fluido que debería ser".

Y, en paralelo, **mejorar el SEO** para traer más tráfico calificado.

## 🧭 Cómo trabajamos (acuerdo)
Para cada etapa: **proponer → aprobar → implementar → verificar → actualizar este plan + memoria**.
Ninguna etapa se da por cerrada sin aprobación explícita del owner. Al aprobar, se marca ✅ y se registra la fecha.

---

## 📊 Criterio de priorización (visión dueño + diseñador experto)
Priorizamos por **impacto para el visitante ÷ complejidad técnica**. Primero lo que más mueve la aguja con menor riesgo. Lo estructural (mayor esfuerzo) va después, ya con datos que lo justifiquen.

| Prioridad | Etapa | Impacto | Esfuerzo | Riesgo |
|---|---|---|---|---|
| **P0** | E0 · Medición base y limpieza | Habilita decidir con datos | Bajo | Bajo |
| **P1** | E1 · Quick wins de checkout | 🔴 Alto (revenue directo) | Bajo-Medio | Bajo |
| **P2** | E2 · Hero visual + identidad base | 🔴 Alto (percepción/marca) | Medio | Bajo |
| **P3** | E4 · SEO técnico (JSON-LD + Core Web Vitals) | 🟠 Alto compuesto (tráfico) | Medio | Bajo |
| **P4** | E3 · Embudo más corto (estructural) | 🔴 Alto (conversión) | Alto | Medio |
| **P5** | E5 · Rediseño visual completo | 🟠 Refinamiento | Alto | Medio |

> Nota de owner: E1 y E2 van primero porque atacan directamente las dos quejas con bajo riesgo. SEO (E4) se intercala antes del rediseño estructural porque su retorno es compuesto y no depende del rediseño. E3 (acortar embudo) es el cambio más rentable pero también el más invasivo: se hace cuando E0 confirme dónde sangra más.

---

## 🗺️ Embudo de compra actual (mapeado en código)
```
Homepage → [clic "Reservar ahora"] → Modal (Fecha/Hora/Personas) → "Agregar al Carrito"
   → Página Carrito → Página Checkout (datos + pago) → Redirección a Flow.cl → Vuelta
```
4 saltos de página + 1 sitio externo. Cada salto es un punto de fuga.

---

# ETAPAS

## 🟡 ETAPA 0 — Medición base y limpieza  · `P0` · Estado: **EN PROGRESO** (rama `mejora-web-etapa0`)
**Por qué primero:** sin baseline no sabemos qué mejora funcionó ni dónde sangra más el embudo.
- [~] Embudo GA4/Meta: el notebook *Aremko Digital Marketing* solo tiene **metas, no datos reales** (objetivo conversión Google Ads >5%, Meta >3%; crecimiento reservas +20/50/100%). **Faltan cifras reales** de add_to_cart→checkout→reserva → requiere export de GA4.
- [~] Core Web Vitals: PageSpeed Insights API sin key está con cuota agotada. Correr manual en pagespeed.web.dev o configurar API key. *(pendiente)*
- [x] Resolver duplicación de `homepage.html`: el archivo `language=ventas/templates/ventas/homepage.html` estaba **vacío** y commiteado por error (Django nunca lo servía). Eliminado. El real es `ventas/templates/ventas/homepage.html`.
- [x] Tina **Yates**: ya no muestra "$0". Es **uso gratuito para todos los huéspedes** → la tarjeta muestra "🎁 Cortesía · Uso libre para todos los huéspedes de Aremko". Fix centralizado en filtro `tina_display` (`es_cortesia`) + `homepage.html`.
- [x] **Decisión Yates = uso libre sin reserva**: el botón "Reservar ahora" se reemplazó por "Uso libre para huéspedes" (no abre modal, no entra al carrito).
**Éxito:** tener números de partida y saber el paso #1 que más pierde gente.

> 📌 Baseline real (GA4 + Core Web Vitals) queda pendiente de un export/acceso. Acordado: avanzar a E1 y **medir el impacto después** con los eventos ya instalados (InitiateCheckout, reservation_completed).

**Baseline de rendimiento medido (2026-05-31, home, móvil aprox.):**
| Métrica | Valor | Lectura |
|---|---|---|
| TTFB (respuesta del servidor) | **~1.03 s** | 🔴 Lento (ideal <0.5s). Server-side: Django/Render con 1 worker gunicorn. Afecta LCP y SEO. |
| Peso del HTML | **132 KB** | 🟠 Alto para solo HTML (mucho contenido inline). |
| Imágenes | 29 (27 con `lazy`) | 🟢 Lazy-loading ya implementado. |
| Carruseles / scripts / CSS | 168 / 10 / 5 | 🟠 Muchos carruseles = DOM/JS pesado. |

→ Palanca clave para E4: **bajar TTFB** (servidor) y **optimizar el hero/LCP**. El lazy-load ya está bien.

## 🟡 ETAPA 1 — Quick wins de checkout  · `P1` · Estado: **EN PROGRESO** (rama `mejora-web-etapa0`)
**Ataca:** abandono directo del carrito, con bajo riesgo.
Archivo principal: `ventas/templates/ventas/checkout.html`
- [x] Reemplazados todos los `alert()` de validación/checkout por banner inline elegante (`#checkoutAlert` + `showCheckoutError()`). Quedan solo 2 fallbacks intencionales.
- [x] Validación de teléfono amable: mensaje de error suavizado (sin "❌"), con ejemplo de formato.
- [x] **Stepper de progreso**: Carrito ✓ → Tus datos → Pago.
- [x] Señales de confianza: candado + "Pago seguro" + tarjetas/WebPay vía Flow + **política de cancelación visible** (48h → 100%; <48h reagenda). Línea de garantía también bajo el botón "Pagar y reservar".
- [x] Mensaje honesto de tranquilidad (no contador falso): la `PendingReservation` se crea al pagar con TTL real de 60 min (`PENDING_RESERVATION_TTL_MINUTES`); en la página de checkout el horario aún no está bloqueado, así que el copy dice "guardamos tu horario mientras finalizas el pago".
- [ ] *(opcional, pendiente)* Reordenar layout: subir el selector de método de pago a la columna del botón (hoy el botón vive en Row 1 y el método en Row 2). Mitigado con la línea de confianza bajo el botón.
**Éxito:** subir la tasa checkout→reserva confirmada vs baseline E0.

> Política de cancelación confirmada por Jorge: **48h antes → reembolso 100%; menos de 48h sin reembolso pero se puede reagendar.**

## ⬜ ETAPA 2 — Hero visual + identidad base  · `P2` · Estado: **PENDIENTE**
**Ataca:** "no refleja lo lindo del lugar". Usa skill `guia-diseno-ui-moderno`.
Archivos: `homepage.html`, `base_public.html` (CSS variables)
- [ ] **Hero a pantalla completa** con foto/video del lugar + tagline ("2 días aquí equivalen a una semana de vacaciones") + CTA + ratings (4.4/4.5).
- [ ] Sistema de diseño mínimo: paleta (verde bosque + madera + acento cálido) y tipografía display, vía variables CSS. Reemplazar el azul Bootstrap default.
- [ ] Botones, tarjetas y secciones con identidad (salir del look "dashboard").
- [ ] Testimonios con foto/nombre real; newsletter rediseñado.
**Éxito:** menor bounce, mayor tiempo en sitio, percepción premium. (Ojo: cuidar performance del hero — coordinar con E4 Core Web Vitals.)

## ⬜ ETAPA 4 — SEO técnico y de contenido  · `P3` · Estado: **PENDIENTE**
**Base existente:** OG/Twitter tags ✅, sitemaps (3 apps) ✅, robots ✅, campos `meta_description`/`seo_title`/`og_image` ✅, blog ✅.
**Gap principal:** no hay datos estructurados JSON-LD.
- [ ] **JSON-LD**: `LocalBusiness`/`HealthAndBeautyBusiness`/`Spa`, `Product`+`Offer` por servicio, `AggregateRating` (usar 4.4/4.5 reales), `FAQPage`, `BreadcrumbList`.
- [ ] **Core Web Vitals**: optimizar imagen del hero (formatos next-gen, `preload`, lazy-load del resto), reducir LCP/CLS.
- [ ] Completar `meta_description`/`seo_title` por servicio (campos ya existen en modelos).
- [ ] `alt` descriptivo en imágenes; revisar sitemaps e internal linking blog ↔ servicios.
- [ ] Páginas locales (Puerto Varas / Los Lagos) con skill `programmatic-seo`.
**Éxito:** mejores posiciones, impresiones y CTR orgánico; rich snippets (estrellas) en Google.

## ⬜ ETAPA 3 — Embudo más corto (estructural)  · `P4` · Estado: **PENDIENTE**
**Ataca:** la causa estructural #1 del abandono (demasiados saltos).
- [ ] Modal de reserva → checkout directo (saltar/fusionar la página intermedia de carrito).
- [ ] "**Arma tu día**": agregar varias experiencias (masaje + tina + …) para la misma fecha sin reabrir el modal cada vez.
- [ ] Revisar el handoff a Flow.cl (reforzar confianza antes de salir del sitio).
**Éxito:** menos pasos por reserva, mayor conversión multi-servicio (ticket alto).

## ⬜ ETAPA 5 — Rediseño visual completo  · `P5` · Estado: **PENDIENTE**
- [ ] Aplicar el sistema de diseño a todo el sitio: galerías inmersivas por tina, secciones, microinteracciones, accesibilidad y móvil pulido.
**Éxito:** consistencia visual premium de punta a punta.

---

## 📌 Bitácora de avances
| Fecha | Etapa | Avance | Aprobado por |
|---|---|---|---|
| 2026-05-30 | — | Diagnóstico inicial + creación del plan | Jorge |
| 2026-05-30 | E0 | Limpieza homepage duplicado (vacío) + Yates "$0" → "Cortesía". Rama `mejora-web-etapa0`. Falta baseline de datos. | pendiente |
| 2026-05-31 | E1 | Quick wins checkout: alertas inline, stepper, confianza, política cancelación, teléfono amable. | pendiente |
| 2026-05-31 | E0+E1 | **Desplegado a producción** (merge a `main` + push, `5cc8f2f`). Templates validados con Django offline (sintaxis OK). Render auto-deploy. | pendiente verificación visual |

## 📎 Referencias
- Diagnóstico base: análisis del sitio en vivo + código (`checkout.html`, `cart.html`, `homepage.html`).
- Tracking ya disponible: `InitiateCheckout` (Meta), `reservation_completed` (GA4), conversión Google Ads.
- SEO actual: `SEO_IMPLEMENTATION_GUIDE.md`, `populate_seo_content.py`, `ventas/sitemaps.py`.
- Notebooks NotebookLM: *Aremko Digital Marketing Strategy 2026*, *DPV SEO Strategy*.
