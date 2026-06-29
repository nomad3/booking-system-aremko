# BRIEF H-048 — Mostrar el texto conversacional de Luna junto al cajón de cotización

> **De:** agente Django (`~/dev/booking-system-aremko`)
> **Para:** agente aremko-cli (`~/Documents/GitHub/aremko-cli.nosync`)
> **Estado Django:** ✅ nada que tocar — el backend YA provee todo. Es **frontend puro**.

---

## 1. El problema (pedido de Jorge, 2026-06-29)

Cuando la cotización queda lista, hoy el cajón **"Cotización lista"** aparece **solo** (con el botón
"Poner cotización en el mensaje"), pero **Luna no presenta ningún texto conversacional** en el chat.
Jorge dice: *"no presenta texto"* — quiere que, al crear la cotización, Luna **además** muestre un
mensaje conversacional para enviar al cliente (ej. *"¡Listo! Te dejo tu cotización para que la
revises con calma 🌿"* + el link), no un cajón mudo.

Ejemplo real: cliente existente pide "tina y masaje para el jueves" → Luna ofrece la Pausa → "si"
→ aparece el cajón con los ítems pero **el campo de respuesta queda vacío** (sin texto de Luna).

## 2. Qué provee el backend (ya en prod, sin cambios)

El endpoint de conversación (`/api/whatsapp/conversation/` + inbox IG/Messenger) devuelve **a la vez**:
- **`sugerencia_agente`**: el borrador conversacional de Luna para ese turno (NO se suprime cuando
  hay propuesta — lo confirmé en `generar_sugerencia`). Tras crear la cotización suele venir algo
  como *"¡Listo! Te preparé la cotización para que la revises 🌿"* (texto, sin link).
- **`propuesta_reserva.url_cotizacion`**: el link firmado de la cotización (lo que hoy inyecta el
  botón "Poner cotización en el mensaje").

> Hoy el front, cuando hay `propuesta_reserva`, muestra el cajón pero **NO** muestra
> `sugerencia_agente`. Ese es el gap.

## 3. Tarea aremko-cli (frontend)

Cuando exista `propuesta_reserva`, además del cajón, **presentar el mensaje conversacional de Luna**
para enviar al cliente. Dos formas (elegí la que quede más limpia en `CotizacionCajon.tsx` /
`ConversacionWhatsApp.tsx`):

- **Opción simple (recomendada):** que el botón **"Poner cotización en el mensaje"** ya no requiera
  click manual obligatorio — **autocargá** en el campo de respuesta el mensaje conversacional que ese
  botón arma hoy (saludo + link de `url_cotizacion`), p.ej.: *"¡Hola, Jorge! 🌿 Te dejo tu cotización
  para que la revises con calma: {url_cotizacion}"*. Así Deborah lo ve listo y solo presiona enviar.
  (Mantené el botón por si lo borró y lo quiere recargar.)
- **Alternativa:** mostrar el texto de `sugerencia_agente` como borrador visible arriba del cajón
  (aparte), y el cajón debajo con el link.

Lo importante para Jorge: que **se vea un texto conversacional listo para enviar** al crear la
cotización, no un cajón mudo. El **contenido del mensaje** (saludo + link) ya lo sabés armar (es lo
que hace "Poner cotización en el mensaje" hoy).

## 4. Criterios de aceptación
1. Al crear la cotización (cliente existente → va directo al cajón), aparece **un texto
   conversacional** listo en el campo de respuesta (o visible como borrador), con el link.
2. Sigue funcionando "Poner cotización en el mensaje" (recargar el texto).
3. `tsc` 0 + `next build` OK.

## 5. Notas
- **NO toca Go** (el endpoint de conversación es passthrough; `sugerencia_agente` y
  `url_cotizacion` ya llegan).
- Backend sin cambios (lo confirmé). Si necesitaras un campo extra, pedímelo.
