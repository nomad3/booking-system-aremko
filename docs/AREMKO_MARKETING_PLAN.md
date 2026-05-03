# Plan Maestro de Marketing — Aremko Spa Boutique

**Versión:** v1.0 · **Inicio:** 2026-05-01 · **Horizonte:** 6 meses (proyectado)

Este es el plan general que guía el trabajo de marketing de Aremko. Las tareas están numeradas por fase. Cada tarea tiene un estado que actualizamos a medida que avanzamos.

**Documentos relacionados:**
- [docs/MARKETING_PLAYBOOK.md](MARKETING_PLAYBOOK.md) — voz, personas, cadencias, KPIs
- [docs/AREMKO_RECURRING_TASKS.md](AREMKO_RECURRING_TASKS.md) — tareas que se repiten

---

## Estados

| Emoji | Estado | Significado |
|---|---|---|
| ⚪ | Pendiente | No iniciada |
| 🟡 | Procesando | En ejecución |
| 🟠 | Parcialmente terminada | Avanzada pero falta cierre |
| 🟢 | Terminada | Completa y validada |
| 🔴 | Bloqueada | Espera dependencia o decisión |

---

## Presupuesto operativo confirmado

**Total publicidad pagada: ~$300 USD/mes** (Meta + Google combinado).

Distribución sugerida (a refinar con datos):
| Canal | Presupuesto inicial | Foco |
|---|---|---|
| **Meta Ads** (Tarea 4.5 + 6.6) | ~$100-150/mes | Boost de Reels orgánicos ganadores + retargeting visitantes web |
| **Google Ads** (Tarea 6.7) | ~$150-200/mes | Branded keywords + long-tail high-intent |

Otros costos fijos ya operando:
- SendGrid Essentials 50K: $19.95/mes (email)
- OpenRouter LLM (análisis IA semanal + futuro Agente Recepcionista): ~$30-50/mes según uso
- cron-job.org: $0 (plan free, suficiente)
- Cloudflare DNS: $0
- Google Search Console / GA4 / Meta Pixel: $0

**Total marketing/tech mensual estimado: $370-420 USD**

## Diagnóstico base (las 3 verdades del 7 Maletas)

1. **Problema #1 del cliente:** estrés laboral + necesidad urgente de desconectar (12+ menciones en reviews)
2. **Diferencial menos saturado:** experiencia 3-en-1 (masaje + tina + cabaña) — solo Aremko en su rango de precio
3. **Objeción crítica que está matando reviews:** inconsistencia de temperatura del agua (3 quejas combinadas)

Todo el plan respeta este diagnóstico. La frase ancla es **"2 días aquí equivalen a una semana de vacaciones"** — debe estar visible en home.

---

## Fase 0 — URGENTE (próximas 2 semanas)

> *No tiene sentido traer 1.000 visitas si la primera review nueva habla de agua tibia.* Esta fase **bloquea** las siguientes.

### 1.1 Resolver inconsistencia de temperatura del agua
- **Estado:** 🟢 terminada (2026-05-03, reportada como resuelta por Jorge)
- **Responsable:** Jorge (operaciones)
- **Prioridad:** ALTA · **Bloqueante:** sí
- **Origen:** 7 Maletas, Maleta 6 (objeción #1)
- **Criterio de éxito:** 0 reviews nuevas mencionando agua tibia en 30 días → monitorear en próximos reportes IA semanales
- **Validación a futuro:** que las próximas encuestas en EncuestaSatisfaccion mantengan cal_temperatura_tina >=4 promedio

### 1.2 Cambiar H1 de la home
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (código)
- **Prioridad:** ALTA · **Bloqueante:** no, pero alta visibilidad
- **Tiempo estimado:** 30 min
- **Origen:** 7 Maletas, Maleta 3 (frase enterrada)
- **Criterio de éxito:** "2 días aquí equivalen a una semana de vacaciones" como H1 visible en hero
- **Sub-tareas:**
  - [ ] 1.2.a Identificar template de hero en home (likely `aremko_blog/templates/home.html` o similar)
  - [ ] 1.2.b Reemplazar H1 actual
  - [ ] 1.2.c Verificar en mobile + desktop

### 1.3 Publicar Garantía Aremko en home
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (código + copy) + Jorge (validación legal)
- **Prioridad:** ALTA
- **Tiempo estimado:** 1-2h
- **Origen:** 7 Maletas, Maleta 7 (oportunidad enorme — nadie la tiene)
- **Criterio de éxito:** Sección "Garantía Aremko" visible en home + página `/garantia/`
- **Texto base:**
  > "Garantía Aremko: si la temperatura del agua no es la prometida (38°C en tinas) o tu experiencia no cumple tus expectativas, te lo compensamos con un masaje o tina adicional sin costo."
- **Sub-tareas:**
  - [ ] 1.3.a Validar texto de garantía con Jorge (¿qué cubre, qué no?)
  - [ ] 1.3.b Crear página `/garantia/` con texto extendido
  - [ ] 1.3.c Agregar badge en home + en páginas de servicio

### 1.4 Estrategia de reviews — pasar de 40 a 80+ en 60 días
- **Estado:** ⚪ pendiente
- **Responsable:** Jorge (ejecución) + Claude (assets)
- **Prioridad:** ALTA
- **Tiempo estimado:** 2 semanas setup + 60 días ejecución
- **Origen:** 7 Maletas, Maleta 5
- **Criterio de éxito:** 80+ reviews en Google Maps al cabo de 60 días
- **Sub-tareas:**
  - [ ] 1.4.a Generar link corto de Google Reviews
  - [ ] 1.4.b Crear tarjeta física con QR para cabañas (impresión 5 unidades)
  - [ ] 1.4.c Definir script para checkout: "¿Nos dejarían reseña? Les mando el link por WhatsApp ahora."
  - [ ] 1.4.d Configurar mensaje WhatsApp post-visita (24h) con link
  - [ ] 1.4.e Capacitar a recepción

### 1.5 Internal links blog ↔ servicios (Tarea 6 blog week 1)
- **Estado:** 🟢 terminada (2026-05-01)
- **Responsable:** Claude (código)
- **Prioridad:** MEDIA
- **Tiempo estimado:** 30 min
- **Origen:** Plan blog week 1, Tarea 6
- **Criterio de éxito:** links visibles desde `/tinas/`, `/alojamientos/`, home al post de blog
- **Sub-tareas:**
  - [x] 1.5.a Link desde `/tinas/` ("Lee la guía completa →") · `category_detail.html` bloque condicional id=1
  - [x] 1.5.b Link desde `/alojamientos/` ("Cómo aprovechar la tina") · `category_detail.html` bloque condicional id=3
  - [x] 1.5.c Sección "Nuevo en el blog" en home con thumbnail · `homepage.html` antes del CTA final
  - [x] 1.5.d Link al blog en footer general · `base_public.html` menú Enlaces

### 1.6 Verificar indexación blog en GSC (Tarea verificación blog week 1)
- **Estado:** ⚪ pendiente
- **Responsable:** Jorge (consulta GSC)
- **Prioridad:** MEDIA
- **Tiempo estimado:** 5 min
- **Criterio de éxito:** post indexado, sitemap "Correcto"

### 1.7 Reescribir copy home con framework "experiencia 3-en-1"
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (copy) + Jorge (revisión)
- **Prioridad:** ALTA
- **Tiempo estimado:** 2-3h
- **Origen:** 7 Maletas, Maleta 4 (diferencial menos saturado)
- **Criterio de éxito:** home comunica "masaje + tina + cabaña" como propuesta principal, no servicios sueltos
- **Sub-tareas:**
  - [ ] 1.7.a Auditar copy actual de home
  - [ ] 1.7.b Reescribir hero, sección de servicios, CTAs
  - [ ] 1.7.c Mover "$190.000 desde / pack completo" como ancla de precio principal

### 1.10 Pasarelas resbaladizas con humedad (alerta de seguridad detectada por IA)
- **Estado:** 🟡 procesando (2026-05-03 — comprando malla antideslizante)
- **Responsable:** Jorge (operaciones)
- **Prioridad:** ALTA · **Origen:** análisis IA semanal del 2026-05-03 (alerta detectada en múltiples encuestas)
- **Criterio de éxito:** instalación completa de malla, 0 menciones futuras a "resbaladizo" en encuestas

### 1.8 WhatsApp Business broadcast del blog (Tarea 7 blog week 1)
- **Estado:** ⚪ pendiente
- **Responsable:** Jorge (ejecución)
- **Prioridad:** BAJA (ya hicimos email + IG)
- **Tiempo estimado:** 10 min
- **Criterio de éxito:** mensaje enviado a lista de difusión

---

## Fase 1 — Fundamentos (semanas 3-6)

### 2.1 Crear `/garantia/` página completa con SEO
- **Estado:** ⚪ pendiente · depende de 1.3
- **Responsable:** Claude
- **Tiempo:** 2h
- **Detalle:** keyword foco "garantía spa Puerto Varas", schema markup FAQ, internal linking

### 2.2 Configurar GA4 events clave
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (código) + Jorge (validación)
- **Tiempo:** 2h
- **Eventos:** `cta_blog_click`, `reservation_started`, `reservation_completed`, `whatsapp_click`, `phone_click`

### 2.3 Crear management command `weekly_marketing_report`
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 4h
- **Detalle:** lee GA4 + GSC API, genera reporte semanal en markdown, envía por Telegram/WhatsApp

### 2.4 Programar agente de los lunes 10am
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (configuración) + Jorge (validación)
- **Tiempo:** 1h
- **Detalle:** agente lee playbook, genera brief con drafts para todos los canales, entrega por Telegram

### 2.5 Auditoría SEO técnica de aremko.cl
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 4h
- **Output:** documento con score Lighthouse, Core Web Vitals, issues técnicos priorizados, fix list

### 2.6 Keyword research inicial (Semrush o Ahrefs)
- **Estado:** ⚪ pendiente · necesita acceso herramienta
- **Responsable:** Jorge (acceso) + Claude (análisis)
- **Tiempo:** 2-3h
- **Output:** CSV de 50-100 keywords KD<30 vol>100 organizadas por cluster (tinas, masajes, cabañas, Puerto Varas)

### 2.7 Crear skill `/blog-aremko` para generación automática de posts
- **Estado:** ⚪ pendiente · depende de 2.6
- **Responsable:** Claude
- **Tiempo:** 4-6h
- **Detalle:** skill que toma keyword del CSV, analiza top 3 competidores, escribe post con voz Aremko, inserta imágenes Pexels, optimiza SEO técnico

### 2.8 Configurar tracking de reviews
- **Estado:** ⚪ pendiente · depende de 1.4
- **Responsable:** Claude
- **Tiempo:** 2h
- **Detalle:** dashboard simple con n° de reviews por semana, score promedio, reviews negativas que requieren respuesta

---

## Fase 2 — Motor de contenido SEO (semanas 7-16)

### 3.1 Publicar 1 blog post / semana usando skill `/blog-aremko`
- **Estado:** ⚪ pendiente · recurrente
- **Responsable:** Claude (generación) + Jorge (revisión + publicación)
- **Tiempo:** 1h por post (con skill)
- **Cadencia:** lunes
- **Meta semana 16:** 10-12 posts publicados

### 3.2 Crear 6 páginas de servicio "Zipper" (servicio × ciudad)
- **Estado:** ⚪ pendiente · depende de 2.6
- **Responsable:** Claude
- **Tiempo:** 6h total
- **Páginas:**
  - `/spa-puerto-varas/`
  - `/spa-puerto-montt/`
  - `/tinas-calientes-puerto-varas/` (ya existe, optimizar)
  - `/masajes-puerto-varas/`
  - `/cabanas-spa-puerto-varas/`
  - `/spa-osorno/`

### 3.3 Crear hub `/blog/` con categorías y arquitectura SEO
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 3h
- **Detalle:** categorías (Tinas, Masajes, Cabañas, Naturaleza, Sustentabilidad), navegación, breadcrumbs

### 3.4 Internal linking automatizado
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 4h
- **Detalle:** management command que detecta menciones de servicios en posts y los enlaza a páginas correspondientes

### 3.5 Schema markup en todas las páginas clave
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 3h
- **Tipos:** LocalBusiness, Service, Review, FAQPage, Article

### 3.6 Republicar 3-4 mejores posts en Medium
- **Estado:** ⚪ pendiente
- **Responsable:** Jorge (cuenta Medium) + Claude (export)
- **Tiempo:** 2h
- **Detalle:** canonical URL apuntando a aremko.cl

---

## Fase 3 — Instagram + TikTok orgánico (semanas 5-24, paralelo a Fase 2)

### 4.1 Validar framework Reels con primeros 4 videos
- **Estado:** ⚪ pendiente
- **Responsable:** Jorge (grabación) + Claude (guion)
- **Tiempo:** 2 semanas
- **Detalle:** 4 Reels con framework Víctor Eras, medir RI, identificar ganador

### 4.2 Implementar DM automation con palabra clave
- **Estado:** ⚪ pendiente
- **Responsable:** Jorge (decisión) + Claude (config)
- **Tiempo:** 3-4h
- **Opciones:** ManyChat ($15-30/mes) o Meta Business Suite nativo

### 4.3 Estrategia de Stories nivel "nutrición"
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (calendario) + Jorge (ejecución)
- **Tiempo:** 1h setup + 5 min/día
- **Detalle:** rotación de tipos (detrás de escena, masajistas, paneles solares, río, comida, clientes)

### 4.4 Lanzar TikTok como espejo de Reels
- **Estado:** ⚪ pendiente · depende de 4.1 validado
- **Responsable:** Jorge
- **Tiempo:** 2h setup
- **Detalle:** crear cuenta @aremkospa, repostear Reels ganadores

### 4.5 Boost orgánico con Meta Ads de Reels ganadores
- **Estado:** ⚪ pendiente · depende de 4.1
- **Responsable:** Claude (estrategia) + Jorge (presupuesto)
- **Tiempo:** 1h setup inicial
- **Presupuesto asignado:** dentro del bucket "$300 USD/mes Meta + Google Ads combinado". Inicialmente ~$100-150/mes a Meta para boosts de Reels ($5-10 USD por Reel × 10-30 boosts/mes según RI)
- **Herramienta sugerida:** instalar [santmun/meta-ads-skills](https://github.com/santmun/meta-ads-skills) en Claude Code para operar campañas Meta vía CLI sin salir del entorno. Setup ~15-20 min cuando se active esta tarea.
- **Pre-requisitos antes de instalar la skill:**
  - 3-5 Reels publicados con datos de RI (Tarea 4.1)
  - Business Manager + Ad Account ya creados (probablemente sí, dado que Meta Pixel `478226496113915` ya está activo en aremko.cl)
  - Decisión final del split mensual entre Meta y Google Ads

---

## Fase 4 — Email marketing avanzado (semanas 8-16)

### 5.1 Auditar lista actual y limpiar (deliverability)
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 3h
- **Detalle:** revisar bounces, hard fails, sin actividad 12 meses, segmentar

### 5.2 Crear 3 segmentos en SendGrid
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 2h
- **Segmentos:**
  - VIP (5+ visitas)
  - Activos (1-4 visitas, último 12 meses)
  - Dormidos (sin visita 12+ meses)

### 5.3 Newsletter mensual a full list — primer envío
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (copy) + Jorge (envío)
- **Tiempo:** 2h
- **Cadencia:** primer lunes de cada mes

### 5.4 Email semanal a "engaged" — secuencia 8 semanas
- **Estado:** ⚪ pendiente
- **Responsable:** Claude (copy) + Jorge (envío)
- **Tiempo:** 4h setup + 30 min/semana
- **Detalle:** 8 emails con valor (artículos del blog) + 1 oferta soft cada 4

### 5.5 Email post-visita automático con review request
- **Estado:** ⚪ pendiente · depende de 1.4
- **Responsable:** Claude
- **Tiempo:** 3h
- **Detalle:** trigger 24h después de checkout, plantilla con link Google Reviews

### 5.6 Email cumpleaños con incentivo
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 2h
- **Detalle:** trigger fecha de nacimiento del cliente con voucher $20-30k descuento

---

## Fase 5 — Conversión y monetización (semanas 12-24)

### 6.1 A/B test del nuevo H1 home (después de 1.2)
- **Estado:** ⚪ pendiente · depende de 1.2 + GA4 con datos
- **Responsable:** Claude
- **Tiempo:** 4h setup + 4 semanas medición

### 6.2 Optimizar funnel de reserva (reducir abandonos)
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 4-6h
- **Detalle:** auditar /reservas/, simplificar pasos, aumentar tasa de cierre

### 6.3 Implementar gift cards como producto principal en home
- **Estado:** ⚪ pendiente
- **Responsable:** Claude
- **Tiempo:** 3h
- **Detalle:** ya existe el sistema, falta destacar en home (especialmente Día Madre, Día Padre, Navidad)

### 6.4 Landing page Black Friday / CyberMonday
- **Estado:** ⚪ pendiente · ejecutar octubre/noviembre
- **Responsable:** Claude
- **Tiempo:** 4h

### 6.5 Programa de referidos
- **Estado:** ⚪ pendiente · evaluar después de 1.4
- **Responsable:** Claude (estrategia)
- **Tiempo:** 2h estrategia + 6h implementación si va

### 6.6 Meta Ads campaña de retargeting
- **Estado:** ⚪ pendiente · depende de Pixel funcionando con eventos (Tarea 2.2 GA4)
- **Responsable:** Claude (estrategia) + Jorge (presupuesto)
- **Tiempo:** 3h
- **Presupuesto:** dentro del bucket Meta de $100-150 USD/mes. Para retargeting específico ~$50/mes
- **Herramienta:** [santmun/meta-ads-skills](https://github.com/santmun/meta-ads-skills) (operación desde Claude Code)
- **Audiencias:**
  - Visitantes web últimos 30 días que NO reservaron
  - Visitantes a /blog/* últimos 60 días
  - Lookalike de clientes que sí reservaron

### 6.7 Google Ads — branded + long-tail
- **Estado:** ⚪ pendiente · evaluar después de keyword research (Tarea 2.6)
- **Responsable:** Claude (estrategia + setup) + Jorge (presupuesto)
- **Tiempo:** 4-6h setup inicial
- **Presupuesto asignado:** dentro del bucket Google de $150-200 USD/mes. Distribución sugerida:
  - **Branded keywords** (50%): "aremko spa", "aremko puerto varas" — defensivo, baratísimo, alta conversión
  - **Long-tail intent** (35%): "tinas calientes puerto varas", "spa parejas puerto varas", "cabaña con tina puerto varas"
  - **Performance Max** (15%): exploratorio
- **Cuenta:** ya existe Google Ads tag `AW-1015703959` activo en el sitio (instalado de antes)
- **Pre-requisitos:**
  - GA4 events configurados (Tarea 2.2)
  - Conversiones definidas y trackeadas
  - Landing pages optimizadas (Tarea 6.2)

---

## Fase 6 — Escala (mes 6+)

### 7.1 Estrategia de backlinks (link building local)
- **Estado:** ⚪ pendiente
- **Detalle:** intercambios con emprendedores Puerto Varas, registros en directorios turísticos, partnerships con hoteles/agencias

### 7.2 Relaciones con prensa local
- **Estado:** ⚪ pendiente
- **Detalle:** contacto con medios Puerto Varas + revistas de turismo + bloggers viajeros

### 7.3 Video largo (YouTube)
- **Estado:** ⚪ pendiente
- **Detalle:** 1 video/mes de 5-10 min con valor, posicionamiento autoridad

### 7.4 Podcast guesting
- **Estado:** ⚪ pendiente
- **Detalle:** Jorge invitado a 2-3 podcasts/trimestre (turismo, emprendimiento, sustentabilidad)

### 7.5 App mobile (evaluar)
- **Estado:** ⚪ pendiente · evaluar tras 6 meses

---

## Tareas absorbidas / pendientes desde el plan blog week 1

| Origen | Estado | Movido a |
|---|---|---|
| Tarea 5: IG + FB orgánico (carrusel + stories) | ⚪ | Recurrente (no Fase 0) — ver [recurring tasks](AREMKO_RECURRING_TASKS.md) |
| Tarea 6: Internal links | ⚪ | 1.5 |
| Tarea 7: WhatsApp broadcast | ⚪ | 1.8 |
| Verificar indexación GSC | ⚪ | 1.6 |
| Verificar sitemap GSC | ⚪ | 1.6 |

---

## Métricas de éxito globales (revisar mensualmente)

| Métrica | Baseline mayo 2026 | Meta 3 meses | Meta 6 meses |
|---|---|---|---|
| Visitas orgánicas/mes | ~ baja (recién instalando GA4) | 2.000 | 8.000 |
| Reviews Google Maps | 40 | 80 | 150 |
| Reservas atribuidas a marketing digital | ~ desconocido | 20/mes | 50/mes |
| Followers Instagram | 59.000 | 65.000 | 75.000 |
| Email engaged segment open rate | ~ desconocido | 35% | 45% |
| Posición keyword "tinas calientes Puerto Varas" | ~ desconocida | top 5 | top 3 |
| Posición keyword "spa Puerto Varas" | ~ desconocida | top 10 | top 5 |
| Conversión web → reserva | ~ desconocida | 1% | 2% |

---

## Cómo trabajamos este plan

1. **Cada lunes** el agente programado entrega brief con drafts (ver [recurring tasks](AREMKO_RECURRING_TASKS.md))
2. **Tareas se trabajan una a una** — no más de 2 en estado 🟡 al mismo tiempo
3. **Cuando una tarea pasa a 🟢**, marcamos en este archivo y movemos a la siguiente por prioridad
4. **Primer lunes de cada mes** revisamos progreso global y ajustamos prioridades
5. **Cualquier idea nueva** que surja: se evalúa si entra como nueva tarea en el plan o se descarta — no improvisamos
