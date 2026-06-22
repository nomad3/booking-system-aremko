# H-036 — Campaña de Google Ads para "Noche de ritual junto al río"

**Pedido por:** Jorge, 2026-06-22
**Dueño:** aremko-cli (arma y carga la campaña en Google Ads)
**Django:** landing + tracking ya listos; nada que tocar salvo que se pida algo del sitio.

## Objetivo
Crear la campaña de Google Ads del producto insignia **Ritual del Río**, replicando
el patrón/estructura de la campaña **Refugio Aremko** que ya armó aremko-cli, y aplicando
el método Sabri Suby.

> **Google Ads = CAPTURA de demanda** (no generación). Le hablamos a quien YA está
> buscando una escapada/spa/tinas en la zona: copy directo, intención alta, menos
> historia que en Meta. (3-17% del mercado "comprando ahora / buscando info".)

## Producto / oferta
- **Noche de ritual junto al río:** cabaña + tina caliente + masaje nocturno + desayuno.
- **$240.000, 2 personas** (pareja). Experiencia 3-en-1 agendable como una unidad.
- **USP / mecanismo único (KEYSTONE):** único en Puerto Varas que junta **río + noche +
  sistema completo** (vs. un hotel frío, una cabaña sola, o las termas públicas llenas).
- Marca: **Aremko Spa Boutique**, lema "Aguas calientes junto al río".

## Destino y conversión (ya listo, no tocar)
- **Landing pública e indexable:** `https://www.aremko.cl/ritual-del-rio/`
  (hero + 3 escenas + reseñas reales de TripAdvisor + oferta + garantía + CTA único).
- **CTA único → WhatsApp** `wa.me/56957902525`.
- **Conversión ya instrumentada (H-034):** evento GA4 **`click_whatsapp_ritual`** en los
  2 botones + **UTM passthrough** (params `ritual_campaign/source/medium`). GA4 `G-T3K4CTD3HJ`.
  → **Importar esa conversión de GA4 a Google Ads** para que la campaña optimice hacia los leads.
- **Mandar UTM en los anuncios** (utm_source=google, utm_medium=cpc, utm_campaign=<nombre>)
  para que el evento atribuya el lead a la campaña y se vea en Informes→Web (columna UTM Campaña).

## Audiencia / geo
- Sur cercano: **Osorno + Puerto Montt + Puerto Varas** (mismo criterio que Meta; excluir
  Santiago/Concepción/Valdivia salvo que se decida ampliar después).
- Parejas, escapadas, aniversarios, bienestar.

## Contenido sugerido (el agente lo afina, espejo de Refugio)
**Temas de keywords (intención alta):**
- "spa puerto varas", "spa con tinas calientes puerto varas"
- "cabaña con tina caliente puerto varas", "tinajas calientes puerto varas / los lagos"
- "escapada romántica puerto varas / los lagos"
- "hotel boutique pareja puerto varas", "noche romántica puerto varas"
- "masaje pareja puerto varas"
- **Negativas:** trabajo, empleo, gratis, curso, spa de uñas/pestañas, segunda mano.

**RSA:** titulares y descripciones con oferta + USP (río + noche + todo resuelto para dos)
+ garantía + CTA ("Reserva por WhatsApp"). Extensiones: sitelinks (Tinas, Masajes,
Cabañas, Gift Card), callouts (Junto al río, Tinas privadas, Desayuno incluido, Solo 5/noche).

## Medición
- Conversión principal = `click_whatsapp_ritual` (importada de GA4).
- Seguir en el dashboard (Informes→Web ya tiene el segmento de la landing + UTM Campaña, H-034).

## Reparto
- **aremko-cli:** arma y carga la campaña completa en Google Ads (estructura espejo de
  Refugio + contenido Sabri + UTM hacia la landing + importar la conversión de GA4).
- **Django:** landing y tracking listos; disponible si se necesita algo del sitio
  (ej. una conversión adicional, un parámetro, etc.).
