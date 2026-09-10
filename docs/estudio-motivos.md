# Estudio de motivos de búsqueda — Micrositios Aremko (Fase 1)

**Fecha:** 2026-08-20 · **Versión:** 1.0 (con un pendiente marcado)
**Fuentes:** BD producción (24 meses, agregada y anónima — `analysis/output/estudio_reservas_bd_2026-08-20.md`), histórico 2020-2024 (31.277 servicios — `analysis/output/historico_*.csv`), encuesta post-visita (n=634), keyword research previo (`ventas/data/aremko_keywords_phase1.md`), catálogo de campañas Meta 2019-2026, gift cards 24 meses.

**Pendiente:** Search Terms Report de Google Ads (la API respondió 404 por versión retirada; `analysis/export_ads.py` ya se corrigió con detección automática de versión — falta re-ejecutarlo en Render). Este pendiente **refina** los motivos 2, 3 y 6; no cambia la recomendación warm-up, que se sostiene en datos propios.

---

## 1. Contexto que fija las reglas del juego (datos, no supuestos)

1. **El negocio cierra por WhatsApp, no por el carrito.** 96,6% de los pagos los registra staff; solo 2,0% de las ventas nacen comprobadamente del checkout web. → La conversión de cada micrositio se mide en **conversaciones WhatsApp**, y el CTA único a `wa.me/56957902525` con texto pre-llenado por sitio es la arquitectura correcta.
2. **La compra es de corto plazo.** Anticipación mediana: tinas **1 día** (32% mismo día, 82% ≤7 días), masajes 2 días, cabañas 4 días (p90 26d). → Las búsquedas que capturan estos motivos son del tipo "para hoy/este fin de semana"; los micrositios deben responder de inmediato (precio visible, horarios hasta medianoche, WhatsApp directo), no pedir formularios.
3. **El fin de semana concentra la demanda.** Sábado ~30% en todas las categorías; viernes+sábado+domingo ≈ 60-65%. Horas: 14h y el bloque nocturno 19-21h en tinas.
4. **Estacionalidad:** febrero es el peak absoluto (344-380 tinas/mes vs ~140-220 en meses normales); enero fuerte; abril y septiembre son valles. Gift cards: diciembre (73-79/mes) y mayo-Día de la Madre (34-42) contra 6-17 en meses valle.
5. **Descubrimiento actual (encuesta):** Instagram 31,5%, ya-cliente 24,6%, recomendación 22,7%, **Google 14,0%**, publicidad 0,5%. → Google orgánico ya es el 4º canal sin haberlo trabajado con captura de intención; ahí apuntan los micrositios.
6. **Volumen vivo 12 meses (BD):** ~2.400 reservas de tina, ~1.900 masajes de relajación, ~550 noches de cabaña. Tinas grupales (Calbuco+Osorno): 321 reservas. Ambientación romántica R1: 50. San Valentín 2026: 35.

## 2. Clasificación de motivos y evidencia

Los términos disponibles provienen del keyword research por Google Suggest (abril 2026) y de los nombres/temas de 90+ campañas Meta históricas; se cruzan con el comportamiento real de reserva. La columna "volumen búsqueda" es cualitativa (Suggest no da números absolutos); se afinará con el Search Terms Report.

| # | Motivo | Términos representativos | Evidencia propia | Estacionalidad | Ticket asociado | Volumen búsqueda (proxy) |
|---|---|---|---|---|---|---|
| 1 | **Romántico / aniversario / escapada en pareja** | "escapada romántica puerto varas", "spa parejas", "noche romántica", "hotel boutique pareja" | Persona 1 = 70% del público; Ambientación R1 (50 res/12m); San Valentín (35); experiencias $110-290k diseñadas para esto; 15+ campañas Meta de romance desde 2019; peak nocturno 19-21h en tinas | Todo el año; picos feb (S. Valentín) y fines de semana | **$110-240k** (experiencias con nombre) | Medio-alto (3 seeds productivas en Suggest) |
| 2 | **Tinajas / jacuzzi / hot tub (producto genérico)** | "jacuzzi puerto varas", "tinajas calientes puerto varas", "hot tub", "cabaña con jacuzzi" | Mayor volumen del negocio (~2.400 res/12m); anticipación 1 día = búsqueda de intención inmediata; insight Suggest: **"jacuzzi" rinde ~5x "tina caliente"**, "tinaja" 4 variantes | Feb peak; invierno sostiene (lluvia = gancho histórico de campañas) | $50-60k (2h/2 pers), sube con complementos | **Alto** (el cluster más productivo del Suggest) |
| 3 | **Masaje Puerto Varas** | "masajes puerto varas", "masaje descontracturante", 7 subtipos con búsqueda diferenciada | 1.895 masajes relax/12m; cuenta Ads dedicada (AW-1767221019) y landing `/masajes/` ya operando | Estable todo el año; feb-mar peak | $40-45k | Alto (10 sugerencias) |
| 4 | **Celebración / grupo (cumpleaños, despedida, amigas)** | "despedida de soltera puerto varas", "panorama cumpleaños con amigas", "spa grupos" | Tinas grupales Calbuco+Osorno: **321 res/12m** con condiciones únicas (4h, sin descorche); ambientaciones 1.064 hist.; decoraciones $38-78k; persona 2 = 20% | Todo el año, sesgo viernes-sábado 19:30 | $100-200k por grupo | Por confirmar con search terms (no estaba en seeds del Suggest) |
| 5 | **Regalo / gift card** | "gift card spa", "regalo para mamá/pareja puerto varas", "qué regalar aniversario" | Picos duros: dic 73-79 GC/mes, may 34-42, nov 37; campañas Meta de regalo cada dic/may desde 2021 | **Fuertemente estacional**: nov-dic, may, feb | $80-90k promedio emitido | Medio (estacional) |
| 6 | **Alojamiento con tina / parada en ruta Ensenada-Petrohué** | "cabañas con tinaja ensenada", "alojamiento con jacuzzi puerto varas", "cabaña camino a ensenada" | ~550 noches/12m; anticipación mediana 4d y p90 26d = planificación de viaje (motivo distinto al resto); Suggest: "cabañas con tinaja ensenada/cerca de puerto varas" | Ene-feb peak turista; findes largos | $160k+ (Noche de Aguas Calientes) | Medio |
| 7 | **Turista extranjero (EN/PT)** | "hot tubs puerto varas", "spa near puerto varas", "chalé com banheira" | Persona 3 = 10%; TripAdvisor activo; sin datos propios de búsqueda aún | Dic-mar | $120-200k | Sin datos — no inventar |
| 8 | **After-office / desconexión sin alojamiento** | "spa de día puerto varas", "panorama after office" | "Pausa junto al Río" existe para esto; 3 sugerencias "spa de día"; bloque 19h fuerte en semana | Jue-vie tarde | $110-130k | Bajo-medio |

## 3. Priorización (1 = primero)

Criterios: ticket × volumen propio demostrado × demanda de búsqueda × NO canibalizar activos existentes de aremko.cl (`/masajes/` con campaña activa, `/tinas/`, blog, landings de experiencias).

| Prioridad | Motivo | Por qué en esa posición |
|---|---|---|
| **1** | Romántico / escapada en pareja (#1) | Máximo ticket, 70% del público real, cero activo SEO genérico propio compitiendo (las landings de experiencias son de marca, no capturan "escapada romántica puerto varas"), inventario de campañas Meta demuestra que el ángulo convierte hace 7 años |
| **2** | Tinajas/jacuzzi genérico (#2) | El mayor volumen de negocio y de búsqueda; el EMD en variante **jacuzzi/tinajas** ataca términos donde aremko.cl no optimiza (su landing es "/tinas/"); anticipación de 1 día = el buscador está listo para reservar |
| **3** | Celebración / grupo (#4) | Producto único (4h sin descorche) con 321 reservas/12m que hoy NO tiene captura de búsqueda dedicada; `/celebraciones/` existe pero como configurador, no como página de intención | 
| **4** | Regalo / gift card (#5) | Estacional pero con picos violentos y sistema de gift cards ya montado; micrositio activable 2 veces al año |
| **5** | Alojamiento en ruta (#6) | Motivo real y distinto (planificación), pero compite con OTAs y el inventario es de solo 5 cabañas — techo bajo |
| **6** | Masajes (#3) | Alto volumen pero **canibalización directa** con `/masajes/` + campaña AW activa: profundizar el activo madre, no abrir EMD |
| **7** | After-office (#8) | Cubierto por "Pausa junto al Río"; mejorar esa landing antes que un dominio nuevo |
| **8** | Extranjero (#7) | Sin datos propios; evaluar tras validar warm-up (versión EN de un ganador, no dominio nuevo) |

## 4. Recomendación warm-up (2 micrositios)

**Warm-up A — motivo romántico:** EMD candidatos (verificar en NIC Chile, en este orden): `escapadaromanticapuertovaras.cl`, `escapadaromanticasur.cl`, `nocheromanticapuertovaras.cl`. Keyword principal: "escapada romántica puerto varas"; secundarias: "spa parejas puerto varas", "noche romántica sur de chile", "aniversario puerto varas". Contenido ancla: la noche de tres actos (sin nombrar "Ritual del Río" como marca, para sostenerse como entidad independiente), precio concreto desde $110k, reseñas TripAdvisor reales, cómo llegar (20 min de Puerto Varas), FAQ. WhatsApp pre-llenado propio del sitio.

**Warm-up B — motivo tinajas/jacuzzi:** EMD candidatos: `tinajaspuertovaras.cl`, `jacuzzipuertovaras.cl` (el insight "jacuzzi 5x" sugiere considerar seriamente la variante jacuzzi; decidir con el Search Terms Report en la mano), `tinascalientespuertovaras.cl`. Keyword principal: "tinajas calientes puerto varas"; secundarias: "jacuzzi puerto varas", "hot tub puerto varas", "tinaja privada pareja". Contenido ancla: tinas privadas junto al río, hasta medianoche, garantía 38°C, precio $50-60k/2h, disponibilidad hoy/mañana (calza con anticipación de 1 día).

**Por qué estos dos:** son los dos motivos con evidencia propia más fuerte en extremos complementarios — A maximiza ticket (experiencias $110-290k) y B maximiza volumen e intención inmediata. Ninguno canibaliza una landing SEO activa del sitio madre. Si tras 4-8 semanas uno duplica al otro en conversaciones WhatsApp/CLP atribuido, se profundiza ese sub-nicho (motivo #3 celebraciones es el siguiente en la cola).

**Calendario sugerido:** construir sept → aire fines de sept-oct → medir oct-nov (temporada sube hacia dic-feb, la ventana de medición es representativa y el ganador queda instalado antes del peak).

## 5. Criterio de corte y duplicación (adelanto Fase 3)

- **Métrica primaria:** conversaciones WhatsApp iniciadas con el texto pre-llenado del sitio (conteo manual/etiqueta en WhatsApp Business + evento GA4-less en Cloudflare Analytics como control de tráfico).
- **Métrica de valor:** reservas atribuidas (el equipo marca en la conversación de dónde vino; cruce con montos).
- **Umbral de decisión a 8 semanas:** el sitio ganador debe generar ≥10 conversaciones atribuibles y ≥2 reservas; si ambos quedan bajo eso, el problema es tráfico (revisar indexación/GBP/link discreto) antes que duplicar nada.
- **Lección Refugio aplicada:** jamás decidir por leads reportados por la plataforma de Ads; solo cuentan conversaciones y reservas verificadas en el negocio.

## 6. Qué falta y cómo se obtiene

| Dato faltante | Cómo obtenerlo | Impacto |
|---|---|---|
| Search Terms Report Google Ads (12m) | Re-correr `analysis/export_ads.py` en Render (ya corregido: autodetecta versión de API; credenciales confirmadas operativas) | Refina elección jacuzzi vs tinajas y confirma volumen de #4 celebraciones |
| Métricas lifetime de campañas Meta | Misma re-corrida (ahora usa `date_preset=maximum`) | Ranking de ángulos creativos que ya convirtieron |
| Disponibilidad EMDs en NIC Chile | Verificación manual en nic.cl (bloqueado desde el entorno de análisis) | Lista final de dominios — decisión de compra del dueño |
| Volumen absoluto de búsqueda | Keyword Planner (con la cuenta Google Ads ya operativa) — opcional | Precisión del proxy Suggest |
