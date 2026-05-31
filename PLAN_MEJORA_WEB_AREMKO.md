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
- [ ] Leer embudo en GA4/Meta: `view_service → add_to_cart → InitiateCheckout → reservation_completed → Purchase`. Cuantificar % de caída por paso. *(pendiente — requiere acceso a datos)*
- [ ] Baseline de métricas: tasa carrito→pago, abandono checkout, Core Web Vitals (LCP/CLS/INP), posiciones SEO clave. *(pendiente)*
- [x] Resolver duplicación de `homepage.html`: el archivo `language=ventas/templates/ventas/homepage.html` estaba **vacío** y commiteado por error (Django nunca lo servía). Eliminado. El real es `ventas/templates/ventas/homepage.html`.
- [x] Tina **Yates**: ya no muestra "$0". Es **uso gratuito para todos los huéspedes** → ahora la tarjeta muestra "🎁 Cortesía · Uso libre para todos los huéspedes de Aremko". Fix centralizado en el filtro `tina_display` (`es_cortesia`) + `homepage.html`.
**Éxito:** tener números de partida y saber el paso #1 que más pierde gente.

> ⚠️ Decisión pendiente (Yates): hoy sigue teniendo botón "Reservar ahora" que abre el modal con precio $0. ¿La Yates debe ser reservable por horario (gratis) o es de uso libre sin reserva? Definir en E0/E1.

## ⬜ ETAPA 1 — Quick wins de checkout  · `P1` · Estado: **PENDIENTE**
**Ataca:** abandono directo del carrito, con bajo riesgo.
Archivo principal: `ventas/templates/ventas/checkout.html`
- [ ] Reemplazar todos los `alert()` (líneas ~736, 897, 911, 937) por feedback inline elegante.
- [ ] Validación de teléfono amable: no bloquear en `blur`, aceptar formatos comunes, validar al enviar.
- [ ] Reordenar layout: **método de pago junto al botón** "Pagar y reservar" (hoy el botón está arriba del selector). Una columna lógica en móvil.
- [ ] **Stepper de progreso** (Paso 1 de 3) en carrito/checkout.
- [ ] Señales de confianza: candado + logos WebPay/tarjetas + "Pago seguro" + **política de cancelación visible**.
- [ ] Mensaje "**Tu horario está reservado por X minutos**" (la PendingReservation puede expirar; comunicarlo reduce incertidumbre).
**Éxito:** subir la tasa checkout→reserva confirmada vs baseline E0.

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

## 📎 Referencias
- Diagnóstico base: análisis del sitio en vivo + código (`checkout.html`, `cart.html`, `homepage.html`).
- Tracking ya disponible: `InitiateCheckout` (Meta), `reservation_completed` (GA4), conversión Google Ads.
- SEO actual: `SEO_IMPLEMENTATION_GUIDE.md`, `populate_seo_content.py`, `ventas/sitemaps.py`.
- Notebooks NotebookLM: *Aremko Digital Marketing Strategy 2026*, *DPV SEO Strategy*.
