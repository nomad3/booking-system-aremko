# Aremko Blog — Fase 1: Keyword Research

**Fecha:** 2026-04-30
**Sitio:** www.aremko.cl
**Stack:** Google Suggest API (público, `hl=es&gl=cl`)
**Seeds:** 15 + 8 derivados = 23
**Sugerencias brutas:** ~50 únicas (post-dedupe)
**Keywords curadas:** 40
**Distribución:** 12 P0 · 16 P1 · 12 P2

---

## 0. Reglas de scope

1. **NO solapar con DPV-Fase 1.** Las 45 keywords de `destino_puerto_varas/data/keywords_phase1.md` (qué hacer, itinerarios, Frutillar, Saltos del Petrohué, lugares neutros) son territorio del medio editorial DPV. Aremko NO las persigue para evitar canibalización.
2. **Intención comercial/experiencial.** Aremko persigue queries con intent transaccional (servicio, alojamiento, experiencia) o sensorial (atmósfera, ritual). No queries informacionales puras.
3. **Voz editorial:** anfitrión / dueño que cuenta el lugar. Humor obligatorio (decisión heredada de DPV-SEO-002 #7).
4. **EEAT angle:** autoridad de primera mano (operamos el spa). No citamos terceros como medio editorial — hablamos desde la tina.

---

## 1. Insights del keyword research

### A) "Jacuzzi" rinde más que "tina caliente" o "hot tub"
La gente busca **jacuzzi** con 5x más variantes que "tina caliente" en Suggest. Aremko vende tinas calientes a leña, pero el mercado busca con el término genérico. Tres consecuencias:
- Cada landing/post debe ranquear las 3 variantes (tina caliente / jacuzzi / hot tub).
- Hay un post explicativo evidente que captura las 3 búsquedas en una.
- "Tinaja" también aparece como sinónimo regional (4 sugerencias) — vale incluirlo.

### B) Brand orgánica detectada
**"aremko spa puerto varas"** aparece como sugerencia de Google → la marca ya tiene rastro orgánico. Defenderla con contenido propio (no solo home).

### C) Competencia visible
Sugerencias mencionan: Hydra Spa, Spa Dreams, Decher Spa, Spa Enjoy, Spa Casino, Cabañas Lawal. Mapeo, no objetivo.

### D) 7 sub-tipos de masaje con búsqueda diferenciada
descontracturante · relajación · reductivo · sensitivo · linfático · facial · pareja. Cada uno = potencial post de servicio o sección de hub.

### E) "Masaje en cabaña" / "masajes hotel" → intent de servicio en alojamiento
Posicionamiento natural para Aremko: masaje servido en la propia cabaña.

### F) "Motel con jacuzzi puerto varas" — nicho privacidad/parejas
Existe pero es lateral. No target principal por imagen de marca boutique.

---

## 2. Sugerencias brutas por seed

### Productivas (≥3 sugerencias)

```
spa puerto varas (10)
  spa puerto varas chile
  hydra spa puerto varas
  spa dreams puerto varas
  aremko spa puerto varas         ← BRAND
  spa masajes puerto varas
  spa enjoy puerto varas
  decher spa puerto varas
  hotel spa puerto varas
  spa casino puerto varas

masajes puerto varas (10)
  masajes puerto varas mejor valorados
  spa masajes puerto varas
  masajes descontracturantes puerto varas
  masajes reductivos puerto varas
  masajes sensitivo puerto varas
  masajes relajantes puerto varas
  masajes linfaticos puerto varas
  masajes hotel puerto varas
  masajes faciales puerto varas

jacuzzi puerto varas (5)
  hotel jacuzzi puerto varas
  motel con jacuzzi puerto varas
  cabaña con jacuzzi puerto varas
  alojamiento con jacuzzi puerto varas

cabañas con tinaja puerto varas (4)
  cabañas con tinaja ensenada puerto varas
  cabañas con tinaja cerca de puerto varas
  cabañas lawal puerto varas con tinaja

hot tub puerto varas (3)
  arriendo hot tub puerto varas
  cabañas con hot tub puerto varas

spa parejas chile (3)
  spa parejas santiago chile
  dia spa parejas santiago chile

spa de día puerto varas (3)
  día de spa puerto varas
  dia de spa dreams puerto varas

tina caliente a leña (2)
  tina caliente con leña

tinas calientes puerto varas (2)
  tinas calientes de puerto varas fotos
```

### Vacías o eco (≤1 sugerencia)
`cabañas con tina caliente puerto varas` · `cabañas para parejas puerto varas` · `escapada romántica sur de chile` · `alojamiento orilla río puerto varas` · `masaje descontracturante puerto varas` · `masaje relajación puerto varas` · `cabañas boutique puerto varas` · `cabañas con jacuzzi sur de chile` · `motel con jacuzzi puerto varas` · `alojamiento con jacuzzi puerto varas` · `diferencia jacuzzi y tina caliente` · `spa parejas puerto varas` · `masaje en cabaña puerto varas` · `masaje pareja puerto varas`

> Eco/vacío ≠ sin demanda. Significa que aún no hay query exacta dominante en Suggest. Es donde el blog **construye demanda nueva** y captura long-tail.

---

## 3. Keywords curadas por cluster

### Cluster TINAS (tina caliente / jacuzzi / hot tub / tinaja)
| Keyword | Prioridad | Intent | Notas |
|---|---|---|---|
| tinas calientes puerto varas | **P0** | Comercial | Producto core Aremko |
| jacuzzi puerto varas | **P0** | Comercial | Variante terminológica más buscada |
| cabaña con jacuzzi puerto varas | **P0** | Comercial | Alojamiento + producto |
| diferencia jacuzzi y tina caliente | **P0** | Informacional | Post explicativo captura 3 términos |
| tina caliente a leña | P1 | Comercial-experiencial | Diferencial Aremko |
| hot tub puerto varas | P1 | Comercial | Variante en inglés |
| alojamiento con jacuzzi puerto varas | P1 | Comercial | Sinónimo |
| cabañas con tinaja puerto varas | P1 | Comercial | Sinónimo regional |
| arriendo hot tub puerto varas | P2 | Comercial | Intent de arriendo, no de estadía |
| cabañas con jacuzzi sur de chile | P2 | Comercial | Geo amplia |
| motel con jacuzzi puerto varas | P2 | Comercial | Nicho privacidad |
| tinas calientes de puerto varas fotos | P2 | Visual | Image SEO |

### Cluster MASAJES
| Keyword | Prioridad | Intent | Notas |
|---|---|---|---|
| masajes puerto varas | **P0** | Comercial | Hub principal |
| masaje descontracturante puerto varas | **P0** | Comercial | Más pedido |
| spa masajes puerto varas | **P0** | Comercial | Crossover spa+masaje |
| masaje en cabaña puerto varas | P1 | Comercial | Servicio en alojamiento |
| masajes relajantes puerto varas | P1 | Comercial | Sub-tipo común |
| masaje pareja puerto varas | P1 | Comercial | Segmento parejas |
| masajes faciales puerto varas | P1 | Comercial | Sub-tipo |
| masajes reductivos puerto varas | P1 | Comercial | Sub-tipo |
| masajes hotel puerto varas | P2 | Comercial | Intent en alojamiento |
| masajes puerto varas mejor valorados | P2 | Comercial | Intent comparativo |
| masajes sensitivo puerto varas | P2 | Comercial | Sub-tipo nicho |
| masajes linfaticos puerto varas | P2 | Comercial | Sub-tipo nicho |

### Cluster SPA / DÍA
| Keyword | Prioridad | Intent | Notas |
|---|---|---|---|
| spa puerto varas | **P0** | Comercial | Hub principal |
| spa parejas puerto varas | **P0** | Comercial | Segmento parejas |
| spa de día puerto varas | P1 | Comercial | Formato sin alojamiento |
| día de spa puerto varas | P1 | Comercial | Variante |
| aremko spa puerto varas | P1 | Branded | Defensa marca |
| hotel spa puerto varas | P2 | Comercial | Intent alojamiento |
| spa parejas chile | P2 | Comercial | Geo amplia |

### Cluster ROMANCE / PAREJAS / ALOJAMIENTO
| Keyword | Prioridad | Intent | Notas |
|---|---|---|---|
| escapada romantica sur de chile | **P0** | Top-funnel | Inspiracional |
| cabañas para parejas puerto varas | **P0** | Comercial | Alojamiento parejas |
| alojamiento orilla río puerto varas | P1 | Comercial | Diferencial Aremko (río Pescado) |
| cabañas boutique puerto varas | P1 | Comercial | Posicionamiento boutique |

### Cluster RIO / SENSORIAL (demanda construida — long tail editorial)
Sin volumen de Suggest, pero territorio editorial natural de Aremko:
- "dormir junto a un río"
- "ruido blanco río naturaleza"
- "cabañas con sonido de río"
- "qué se siente dormir cerca del agua"

> Estas keywords NO compiten en SERP por volumen pero capturan engagement profundo, brand affinity y backlinks orgánicos.

---

## 4. Top 12 P0 (orden de publicación recomendado)

| # | Keyword target | Cluster | Tipo de post |
|---|---|---|---|
| 1 | tinas calientes puerto varas | TINAS | Pillar comercial-experiencial |
| 2 | diferencia jacuzzi y tina caliente | TINAS | Explicativo (captura 3 términos) |
| 3 | masajes puerto varas | MASAJES | Hub guía |
| 4 | escapada romantica sur de chile | ROMANCE | Top-funnel persuasivo |
| 5 | masaje descontracturante puerto varas | MASAJES | Servicio específico |
| 6 | spa de día puerto varas + spa parejas pv | SPA | Comparativo formatos |
| 7 | jacuzzi puerto varas | TINAS | Refuerzo terminológico |
| 8 | cabaña con jacuzzi puerto varas | TINAS | Alojamiento + producto |
| 9 | spa masajes puerto varas | MASAJES | Crossover servicio |
| 10 | cabañas para parejas puerto varas | ROMANCE | Alojamiento parejas |
| 11 | spa puerto varas | SPA | Pillar SPA |
| 12 | spa parejas puerto varas | SPA | Segmento parejas |

---

## 5. Plan publicación 8 semanas (anti-spike)

| Sem | Post | Target principal | Cluster | Voz |
|---|---|---|---|---|
| 1 | "Tinas calientes en Puerto Varas: la guía que tu lumbar ya estaba pidiendo" | tinas calientes puerto varas | TINAS | Anfitrión + humor |
| 2 | "Tina caliente vs jacuzzi vs hot tub: por qué te están vendiendo lo mismo con tres nombres" | diferencia jacuzzi/tina | TINAS | Explicativo + asides |
| 3 | "Masajes en Puerto Varas: cuál pedir según cómo llegaste el viernes" | masajes puerto varas | MASAJES | Diagnóstico humorado |
| 4 | "Escapada romántica al sur de Chile: por qué Puerto Varas le gana a Pucón en mayo" | escapada romántica sur | ROMANCE | Top-funnel + comparación |
| 5 | "Masaje descontracturante: qué pedir cuando llegaste con el cuello hecho un nudo" | masaje descontracturante | MASAJES | Servicio + auto-deprecación |
| 6 | "Spa de día vs spa con alojamiento vs día spa para parejas: 3 formatos que la gente confunde" | spa de día / parejas | SPA | Comparativo |
| 7 | "Dormir junto a un río ruidoso: ciencia, leyenda y por qué nadie quiere despertarse" | (long-tail editorial río) | RIO | POV / sensorial |
| 8 | "La tina caliente a leña: el ritual que los japoneses inventaron y los alemanes copiaron en Frutillar" | tina caliente a leña | TINAS | Cultural + producto |

**Cadencia:** 1 post/semana sostenido tras ramp inicial. Si DPV está saliendo en paralelo (decisión pendiente), staggear: lunes Aremko, jueves DPV — o mover Aremko a quincenal hasta validar capacidad.

---

## 6. Hipótesis a validar offline (Ubersuggest 3/día gratis)

Top 3 candidatos a validación de volumen:
1. `tinas calientes puerto varas`
2. `jacuzzi puerto varas`
3. `masajes puerto varas`

Si volumen mensual >100 → P0 confirmado.
Si volumen mensual 30-100 → P1, sin urgencia.
Si <30 → ajustar prioridad pero NO descartar (long-tail comercial sigue convirtiendo).

---

## 7. Diferencias estratégicas vs blog DPV (recordatorio)

| Eje | DPV | Aremko |
|---|---|---|
| Voz | Travel writer | Anfitrión / dueño |
| EEAT | Cita terceros | Primera mano |
| Cierre | Sin venta | Soft CTA a reserva |
| Keywords | Informacional geo | Comercial servicio + experiencial sensorial |
| Cannibalization risk | — | NO tocar las 45 keywords DPV |

**Regla de oro:** si la keyword aparece en `destino_puerto_varas/data/keywords_phase1.md`, NO escribir post de Aremko sobre ella. Si necesitamos cubrir tema relacionado, linkeamos al post DPV (cross-domain link interno entre los dos sitios cuando estén ambos vivos).

---

## 8. Próximos pasos

- [ ] **Decidir cadencia paralelo vs secuencial vs quincenal Aremko** (input owner)
- [ ] **Validar top 3 P0 con Ubersuggest** (offline, 3/día)
- [ ] **Definir voz editorial Aremko** (entrevista al owner — registro "anfitrión" vs registro "travel writer" de DPV)
- [ ] **Reusar modelo `BlogPost` de DPV** → app `ventas/blog/` o nueva app `aremko_blog/` con misma estructura (BlogPost + admin + sitemap + JSON-LD)
- [ ] **Decisión arquitectura URL:** `aremko.cl/blog/<slug>/` (consistente con DPV)
- [ ] **Primer post:** "Tinas calientes en Puerto Varas: la guía que tu lumbar ya estaba pidiendo"

---

**Origin session:** Continuación post-compaction de DPV-SEO-002 Fase 1. Decisión "Aremko etapa posterior" levantada por owner 2026-04-30 → arrancamos Fase 1 Aremko mismo día.
