# Plan Semana 1 — Lanzamiento Blog Aremko

**Objetivo**: tráfico calificado al post #1 + infraestructura medible para los siguientes posts.
**Horizonte**: 7 días.
**Costo**: $0 (todo orgánico esta semana).
**Responsable**: Jorge.

---

## Estado de medición ANTES de empezar

| Herramienta | Instalado | Mide qué |
|---|---|---|
| Meta Pixel `478226496113915` | ✅ Sí | PageView por URL (visible en Events Manager) |
| Google Ads tag `AW-1015703959` | ✅ Sí | Conversiones de campañas Ads (NO sesiones generales) |
| Google Analytics 4 (GA4) | ❌ **No** | — |
| Google Search Console (GSC) | ❓ Verificar | Impresiones + clicks orgánicos |

**Implicancia**: hoy puedes ver visitas en Meta Pixel pero no tienes el dashboard estándar (sesiones, tiempo en página, scroll, fuentes de tráfico). Tarea #1 esta semana = instalar GA4.

---

## Tarea 1 — Instalar Google Analytics 4 (GA4) en aremko.cl

**Tiempo**: 15 min · **Bloqueante**: sí (todo lo demás depende de esto para medir)

### Pasos

1. Entrar a https://analytics.google.com con `aremkospa@gmail.com`
2. **Admin** (rueda abajo izquierda) → **Crear cuenta** → "Aremko Spa Boutique"
3. **Crear propiedad** → "aremko.cl" → zona horaria Santiago, moneda CLP
4. **Plataforma**: Web → URL `https://www.aremko.cl` → nombre del stream "Aremko web"
5. Copia el **Measurement ID** (formato `G-XXXXXXXXXX`)
6. Pídele a Claude que lo instale en `ventas/templates/ventas/base_public.html` (junto al fbq existente). Acción de 1 commit.

### Configuración recomendada en GA4 después

- **Eventos clave** (conversions): `purchase`, `generate_lead`, `cta_blog_click`
- **Audiencia "Lectores blog"**: usuarios que vieron `/blog/*` (la creas con un click)
- **Reporte personalizado "Blog content"**: filtro por path `/blog/` → métricas: views, engaged sessions, avg engagement time

---

## Tarea 2 — Google Search Console (GSC)

**Tiempo**: 10 min · **Bloqueante para SEO**: sí

### Pasos

1. https://search.google.com/search-console con `aremkospa@gmail.com`
2. **Agregar propiedad** → tipo "Dominio" → `aremko.cl`
3. Verificar vía **DNS TXT en Cloudflare** (es donde está el dominio). Pega el TXT que te da Google → propaga en ~2 min.
4. Una vez verificado: **Sitemaps** → enviar `https://www.aremko.cl/sitemap.xml` (ya existe en el código).
5. **URL inspection** → pegar `https://www.aremko.cl/blog/tinas-calientes-puerto-varas/` → click "Request indexing".

### Qué mide GSC

- **Impresiones**: cuántas veces tu URL aparece en resultados de Google (aunque no le hagan click)
- **Clicks**: cuántos llegaron desde Google
- **CTR**: clicks ÷ impresiones
- **Posición promedio**: en qué puesto aparece para cada keyword

> ⏱️ Los datos en GSC tardan 2-5 días en aparecer la primera vez. Es normal.

---

## Tarea 3 — Google Business Profile (GBP) post

**Tiempo**: 10 min · **Impacto**: aparece en búsquedas locales y en Google Maps

### Pasos

1. https://business.google.com con `aremkospa@gmail.com`
2. Seleccionar la ficha "Aremko Spa Boutique"
3. **Publicar actualización** → tipo "Novedades"
4. **Foto**: una de las tinas con río de fondo
5. **Texto** (copy listo, pegar tal cual):

```
Nuevo en el blog: la guía honesta de tinas calientes en Puerto Varas que escribimos
para quien busca ritual real, no jacuzzi de hotel. Aerotermia + paneles solares,
sensores con tope a 40°C, garantía si llega a 37°C o menos, y el río Pescado
sonando todo el año a metros del agua.

Léela en: https://www.aremko.cl/blog/tinas-calientes-puerto-varas/
```

6. **Botón**: "Más información" → URL del post

> Repetir cada 7 días con cada post nuevo. Google premia frecuencia de actualización en GBP para ranking local.

---

## Tarea 4 — Newsletter a 3.000 clientes

**Tiempo**: 30 min (redacción + envío) · **Impacto inmediato**: 50-200 visitas el primer día

### Estrategia de envío

- **NO mandes a los 3.000 de golpe**. Riesgo: spam complaints, baja deliverability futura.
- **Segmenta**: enviar primero a quien YA visitó Aremko (clientes con reservas pasadas) → 800-1.200 personas. Tasa de apertura altísima.
- **48h después**: enviar al resto del listado (los que solo dejaron correo pero no han venido).

### Asunto del mail (3 opciones, A/B si tu plataforma deja)

1. `Escribimos la guía honesta de tinas calientes en Puerto Varas`
2. `Por qué nuestras tinas no usan leña (y por qué eso te importa)`
3. `La única tina con garantía de temperatura en Puerto Varas`

### Cuerpo del mail (copy listo)

```
Hola [nombre],

Si nos conoces, sabes que llevamos años mejorando lo que pasa adentro de
una tinaja en el sur de Chile. Esta semana publicamos algo que llevábamos
tiempo queriendo escribir: una guía completa, sin marketing inflado, sobre
tinas calientes en Puerto Varas.

La hicimos para responder lo que la gente nos pregunta seguido:
· ¿A qué temperatura es ideal?
· ¿Cuánto rato me quedo?
· ¿Por qué Aremko no usa leña? (paneles solares + aerotermia)
· ¿Qué pasa si llego y la tina está fría? (te devolvemos el dinero)
· ¿Hasta qué hora se puede reservar?

→ Léela acá: https://www.aremko.cl/blog/tinas-calientes-puerto-varas/?utm_source=newsletter&utm_medium=email&utm_campaign=blog-post-1

Si te dieron ganas de venir esta semana, recordatorio: domingo a jueves
la cabaña con tina caliente sale $110.000.

Reservas: https://www.aremko.cl/alojamientos/

Nos vemos junto al río,
Jorge
Aremko Spa Boutique
```

### UTM tracking — IMPORTANTE

El link al post lleva `?utm_source=newsletter&utm_medium=email&utm_campaign=blog-post-1`. Esto te permite ver en GA4 (una vez instalado) **exactamente** cuántas visitas vinieron del email vs orgánico vs social. Sin UTM, no hay forma de distinguirlo.

Cada canal debe tener su UTM diferente:
- Newsletter: `?utm_source=newsletter&utm_medium=email&utm_campaign=blog-post-1`
- Instagram: `?utm_source=instagram&utm_medium=social&utm_campaign=blog-post-1`
- Facebook: `?utm_source=facebook&utm_medium=social&utm_campaign=blog-post-1`
- WhatsApp: `?utm_source=whatsapp&utm_medium=chat&utm_campaign=blog-post-1`

---

## Tarea 5 — Instagram + Facebook (orgánico)

**Tiempo**: 45 min total · **Impacto**: depende del engagement de tu cuenta

### Instagram — 1 post + 3 stories

#### Post de feed (carrusel de 4 slides)

**Slide 1**: foto de la tina con río. Texto encima:
```
Las tinas que no usan leña.
Y por qué eso importa.
```

**Slide 2**: foto de los paneles solares. Texto:
```
48 paneles solares.
Más de un año funcionando.
Aerotermia que extrae calor del aire.
Cero combustión.
```

**Slide 3**: foto del río Pescado. Texto:
```
A metros del único río que suena
365 días al año en Puerto Varas.
Ruido blanco natural.
```

**Slide 4**: cierre. Texto:
```
Garantía:
si tu tina llega a 37°C o menos,
es gratis.

Léelo todo (link en bio).
```

**Caption**:
```
Escribimos una guía honesta sobre tinas calientes en Puerto Varas. Sin
marketing inflado, sin "experiencia única" en mayúscula. Lo que de verdad
importa: cómo se calientan, hasta qué hora abrimos (medianoche), por qué
estar al lado del río Pescado cambia todo, y cuál es nuestra garantía si
algo sale mal.

Link en bio. ↑
.
.
.
#PuertoVaras #TinasCalientes #SpaBoutique #SurDeChile #RioPescado #Aremko
```

**Link en bio**: actualizar a `https://www.aremko.cl/blog/tinas-calientes-puerto-varas/?utm_source=instagram&utm_medium=social&utm_campaign=blog-post-1`

#### Stories (3, distribuidas en 48h)

1. **Story 1** (día 1, mañana): screenshot del título del post + sticker "Nuevo blog" + sticker "link" hacia el post.
2. **Story 2** (día 1, tarde): video de 5s de la tina humeando con río de fondo + texto "abierto hasta las 12 de la noche" + sticker link.
3. **Story 3** (día 2): captura de la sección "garantía 37°C" + texto "esto no lo hace nadie en Puerto Varas" + sticker link.

### Facebook — copia del post de IG con caption más larga

Puedes copiar el carrusel y caption. Facebook permite captions más largas, así que pega los primeros 3 párrafos de la intro del blog + link.

---

## Tarea 6 — Internal links desde el sitio

**Tiempo**: 20 min · **Impacto**: SEO (Google entiende que el blog es importante)

### Lugares donde agregar link al post nuevo

1. **Página `/tinas/`**: en algún lugar visible, párrafo o card que diga "¿Quieres saber más sobre tinas calientes en Puerto Varas? Lee la guía completa →" linkeando al post.
2. **Página `/alojamientos/`**: similar, "Las cabañas incluyen tina caliente. Cómo aprovecharla → guía"
3. **Homepage `/`**: sección destacada "Nuevo en el blog" con título + thumbnail + link.
4. **Footer**: agregar link al blog en el footer general (esto ya debería estar, pero verifica).

> Estas ediciones son código (template HTML). Pídele a Claude la próxima sesión: "agrega internal links al post de tinas desde /tinas/, /alojamientos/ y home".

---

## Tarea 7 — WhatsApp Business (manual)

**Tiempo**: 10 min · **Impacto**: alta conversión, audiencia tibia

Si tienes lista de difusión de WhatsApp Business (clientes que dieron consentimiento):

```
Hola, te cuento que publicamos en el blog de Aremko una guía sobre tinas
calientes que veníamos queriendo escribir hace tiempo. Si alguna vez te
interesó saber por qué nuestras tinas no usan leña o cuál es la diferencia
real con un jacuzzi de hotel, está acá:

https://www.aremko.cl/blog/tinas-calientes-puerto-varas/?utm_source=whatsapp&utm_medium=chat&utm_campaign=blog-post-1

Recordatorio: domingo a jueves cabaña con tina sale $110.000.

Cualquier duda me escribes.
Jorge
```

---

## Cómo voy a medir el éxito de esta semana

| Métrica | Dónde la veo | Meta Semana 1 |
|---|---|---|
| **Visitas al post** | GA4 (una vez instalado) | 500-1.500 |
| **Tiempo promedio en página** | GA4 | >2 min (el post es largo) |
| **Visitas desde email** | GA4 → fuente `newsletter` | 100-300 |
| **Visitas desde Instagram** | GA4 → fuente `instagram` | 50-200 |
| **Impresiones en Google** | GSC → URL específica | 100-500 (la primera semana es baja) |
| **Reservas atribuidas** | Sistema interno + UTMs | 2-5 (si conviertes 0.3-1% del tráfico) |
| **Clicks en CTA del post** | Meta Pixel evento custom (configurar) | 30-80 |

---

## Checklist Domingo (cierre Semana 1)

- [ ] GA4 instalado y registrando datos
- [ ] GSC verificado, sitemap enviado, post indexado
- [ ] Post de Google Business Profile publicado
- [ ] Email enviado a segmento 1 (clientes con reserva pasada)
- [ ] Email enviado a segmento 2 (resto)
- [ ] Post Instagram + 3 stories publicados
- [ ] Post Facebook publicado
- [ ] Internal links agregados desde /tinas/, /alojamientos/, /
- [ ] WhatsApp difusión enviada
- [ ] Reporte semanal: ¿cuántas visitas? ¿cuánto tiempo? ¿alguna reserva trazable al post?

---

## Lo que NO se hace esta semana (para no diluir foco)

- ❌ Meta Ads boost del post (semana 2-3, una vez tengamos baseline orgánico)
- ❌ Backlinks externos (semana 2-3)
- ❌ Republicar en Medium (semana 2)
- ❌ Post #2 del blog (lunes próximo, según cadencia acordada)

---

## Para Claude la próxima sesión

Si esta semana implementas todo y vuelves a la sesión, las tareas técnicas
que puedo automatizar son:

1. Instalar GA4 en `base_public.html` (solo necesito el Measurement ID `G-XXXXXXXXXX`)
2. Agregar internal links desde `/tinas/`, `/alojamientos/` y home
3. Configurar evento custom de Meta Pixel para "click en CTA del blog"
4. Crear management command que genere el reporte semanal de visitas (cruzando GA4 API con reservas internas)

Dime cuál arrancar.
