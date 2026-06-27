# BRIEF H-041 — Landing "Pausa junto al río" (`/pausa-junto-al-rio/`)

> Pedido de Jorge (2026-06-26, plan de campañas Ritual + Pausa en Meta y Google). Falta una
> landing propia para anunciar la **Pausa junto al río** en ambas plataformas. Reusa el molde
> de `/ritual-del-rio/` (`ritual_rio_landing.html`) y `/refugio/`. **100% Django** (aremko-cli
> solo entrega este brief + copy; no toca nada de código Django).

## Objetivo
Página de aterrizaje boutique para la **Pausa junto al río** (la experiencia de ENTRADA: tina +
masaje en pareja el MISMO día, sin alojamiento). Destino de los anuncios de Google + Meta. CTA a
WhatsApp (igual que Ritual/Refugio), con medición.

## Oferta (confirmada por Jorge 2026-06-26)
- **Producto:** tina caliente privada + **masaje en pareja**, el mismo día, junto al río. SIN alojamiento.
- **Precio: $110.000 dom-jue** / $130.000 vie-sáb, para **2 personas**. (Es el pack tina+masaje "Pausa
  junto al río" que ya usa Luna — `packs.py` `nombre_experiencia`.)
- **Para 2 personas.** Check-in por coordinar (tarde). Pago por transferencia (lo coordina Deborah).

## Estructura (reusar `ritual_rio_landing.html`)
Mismas secciones/estilo que el Ritual, con el copy de abajo. Fotos reales: tina humeando + detalle de
masaje (Cloudinary, recorte `g_auto` como en Ritual). Reusar las **reseñas reales** que ya están en
Ritual/Refugio (TripAdvisor/Google 4,5★).

## Copy (listo para montar — método Sabri, voz boutique, español de Chile)

**HERO**
- Título: **Pausa junto al río**
- Subtítulo: **Tina caliente + masaje en pareja, en una sola tarde.**
- Bajada: Unas horas para desconectar de verdad — sin viajar lejos ni quedarse a dormir. Llegan, se
  meten a la tina caliente junto al río, reciben un masaje para los dos… y salen como nuevos.
- Precio visible: **Desde $110.000 para dos (domingo a jueves).**
- CTA: **Reserva por WhatsApp**

**QUÉ INCLUYE**
- ♨️ Tina caliente privada junto al río
- 💆 Masaje en pareja (relajación o descontracturante)
- 🌿 El sonido del río Pescado y el bosque nativo

**POR QUÉ (mecanismo único)**
- No necesitas un fin de semana entero ni gastar una fortuna para cortar la rutina. La **Pausa** es
  medio día de spa real junto al río: tina caliente + masaje para los dos, todo listo cuando llegan.
- No es una piscina temperada. No son las termas llenas de gente. Es **agua caliente privada + manos
  expertas**, junto al río, solo para ustedes.

**PRECIO**
- Pausa dom-jue: **$110.000** (2 personas)
- Pausa vie-sáb: **$130.000** (2 personas)

**CTA FINAL**
- "Aparta tu Pausa por WhatsApp 👇" → botón WhatsApp.

## Técnico (alinear con Ritual/Refugio)
- Ruta `path('pausa-junto-al-rio/', pausa_landing_view, name='pausa_landing')` + view + template
  `pausa_landing.html`.
- **CTA WhatsApp:** botón `wa.me` al número oficial **56957902525** ([[numeros-contacto-hardcoded]] —
  verificar que sea el correcto) con mensaje prellenado ("Hola, quiero reservar la Pausa junto al río").
- **Medición:** evento GA4 **`pausa_whatsapp_click`** (params `pausa_campaign/source/medium`, espejo
  del `click_whatsapp_ritual`) en los botones WhatsApp + **Meta Pixel `478226496113915`** (PageView +
  Lead al click). Para el dashboard aremko-cli, mismo patrón que Ritual (H-034).
- **Visibilidad:** indexable + en menú/home como el Ritual (config opcional tipo `RitualRioLandingConfig`,
  a tu criterio; o simple si no amerita modelo).
- `{% localize off %}` en cualquier JSON-LD/precio inline ([[jsonld-locale-decimal]]).

## Fuera de alcance
- Las campañas Google/Meta de Pausa las arma aremko-cli (copy + keywords) cuando la landing esté lista.
- Gift card / pago online directo: no (igual que Ritual, es por transferencia/WhatsApp).
