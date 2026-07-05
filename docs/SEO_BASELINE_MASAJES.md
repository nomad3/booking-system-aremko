# SEO Baseline — /masajes/ (previo al swap a landing "Cinco Sentidos")

> Capturado 2026-07-05 desde https://www.aremko.cl/masajes/ (versión catálogo,
> `category_detail_boutique.html`). Referencia para verificar no-regresión SEO tras el
> swap a `masajes_landing.html`. La versión antigua queda accesible en `?classic=1`.

## Title (de SEOContent.meta_title, categoría id=2)
"Masajes en Puerto Varas junto al río | Aremko Spa Boutique"
→ SE CONSERVA en la landing nueva (mismo seo_content).

## H1/H2 actuales → nueva landing
- H1: "Masajes" → CAMBIA a "Un masaje para los cinco sentidos" (keyword "masaje"
  presente; title y contenido conservan "Masajes en Puerto Varas"). Riesgo bajo,
  decisión consciente (H1 emocional + title SEO).
- H2 "Nuestros Masajes" → equivalente: "Elige tu técnica"
- H2 "Sesiones Privadas con Terapeuta Especializado" → integrado en técnicas
- H2 "Acerca de Masajes" → SE CONSERVA (bloque SEO al final, mismo contenido_principal)
- H2 "Beneficios de Nuestros Masajes" → SE CONSERVA (mismo get_beneficios)
- H2 "Preguntas Frecuentes" → SE CONSERVA (las 6 de seo_content + 2 nuevas estáticas)
- H2 "¿Listo para tu experiencia de relajación?" → equivalente CTA final

## FAQ actuales (seo_content, se conservan las 6 + JSON-LD)
1. ¿Qué tipo de masaje es mejor para mí?
2. ¿Cuánto tiempo duran las sesiones de masaje? (50 minutos)
3. ¿Los masajistas son profesionales certificados?
4. ¿Puedo elegir el género del terapeuta?
5. ¿Qué debo hacer antes de mi masaje?
6. Cómo llegar y tienen traslado hasta Aremko? (ruta 225 km 19, retén Río Pescado,
   4 km al Volcán Calbuco; transfer coordinable)
+ NUEVAS (estáticas en template): ¿El masaje es desnudo? (ropa interior) ·
  ¿Hay que caminar entre los espacios? (pasarelas, es parte del circuito)

## Contenido principal (seo_content.contenido_principal — SE CONSERVA ÍNTEGRO)
"En Aremko Spa Puerto Varas, nuestros masajes son mucho más que un simple
tratamiento..." (3 párrafos: personalización, aceites orgánicos, salas/ambiente).

## Beneficios (seo_content — SE CONSERVAN)
1. Alivio del Dolor · 2. Reducción del Estrés · 3. Mejora del Sueño

## Precios visibles hoy (por persona)
Relajación o Descontracturante $40.000 (online) · Piedras Calientes $45.000 ·
Drenaje Linfático $45.000 · Tui-Na $45.000 · Deportivo $45.000 · Tailandés $40.000
— todos 50 min, IVA incluido. La landing nueva los muestra pareja-first
($80.000 pareja base; Pausa $110.000/$130.000) manteniendo el por-persona visible.

## Rutas
- /masajes/ → landing nueva (masajes_landing.html)
- /masajes/?classic=1 → catálogo actual (category_detail_boutique) — booking modal
  online sigue viviendo aquí; la landing enlaza con ancla #servicios-categoria.
- Canonical: sin cambio (https://www.aremko.cl/masajes/).
