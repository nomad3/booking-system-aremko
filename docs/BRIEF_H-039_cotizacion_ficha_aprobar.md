# H-039 — Cotización boutique + Aprobar (Reserva-cliente-digital, Fase 3)

> Continuación de la **Ficha de Reserva del cliente** (Fase 1, ya en prod, commit `9ddac61`/`64b2207`).
> Esta fase agrega la **cotización** como página boutique con botón **Aprobar** que crea la
> reserva automáticamente, más el flujo de envío con Luna y Deborah.

## Objetivo

Reemplazar la cotización de texto plano (staff, copia-pega) por una **página boutique** (misma
identidad de la Ficha) que el cliente abre con un link, revisa, y **Aprueba** con un botón. Al
aprobar, la reserva se crea **automáticamente** y el cliente pasa a su Ficha.

## Flujo end-to-end (decidido con Jorge, 2026-06-26)

1. Luna conversa y arma el carrito. Cuando la conversación de servicios está **completa**,
   **Luna pregunta**: *"¿Te gustaría que te envíe la cotización?"*.
2. Cliente dice **sí** → Luna confirma el carrito → se crea la **`PropuestaReserva`** (ya existe
   este paso) → en el **cajón** aparece un **borrador con el link de cotización** (texto corto +
   link), no el banner "Crear reserva".
3. **Deborah revisa y envía** el link (filtro humano; coherente con `WhatsAppAgentConfig.modo='borrador'`).
4. Cliente abre el link → ve la **cotización boutique** (servicios + total) → toca **Aprobar**.
5. Aprobar → **crea la `VentaReserva` automáticamente** (idempotente) → redirige al cliente a su
   **Ficha** (estado "Pendiente de pago").
6. En paralelo, en el cajón Deborah ve el **resumen de la reserva creada** (banner) → si está bien,
   **envía el link de la Ficha**; si hay error (duplicado, etc.), lo corrige en el admin y luego
   envía. (La creación ya NO pasa por la aprobación de Deborah; ella revisa y envía.)

## Decisiones cerradas (recap)

- **Formato = link** (no PDF, no texto): es el único que soporta el botón Aprobar interactivo y se
  renderiza vivo desde Django. Mensaje corto + tarjeta de preview (OpenGraph) en WhatsApp.
- **Fuente de verdad = Django**: la cotización se renderiza desde la `PropuestaReserva` (precios
  reales de `Servicio.precio_base`, total, línea "Descuento de servicios"); NUNCA del texto del chat.
- **Servicios** los agrega solo el staff en el admin (el cliente no ve disponibilidad de masajistas).
- **Ficha read-only**; **comanda** = la que ya existe, se cierra cuando `estado_reserva='checkout'`.
- **Estados de pago** existentes: Pendiente / Parcialmente pagada / Pagada.

## Piezas a construir

### A. Django (agente Django)
1. **Refactor seguro de la creación**: extraer la creación propuesta→reserva que hoy está inline en
   `ventas/views/luna_api_views.py::crear_reserva` (idempotente: si `propuesta.estado=='creada'`
   devuelve la existente) a una función de servicio `crear_reserva_desde_propuesta(propuesta)` que
   llamen TANTO `crear_reserva` (API, sin cambiar su contrato) COMO la nueva vista web de Aprobar.
   Probar en Docker que la API sigue idéntica.
2. **Página de cotización** (cara al cliente): token firmado sobre `propuesta_id`
   (`django.core.signing`, mismo patrón que la Ficha). Reusa el diseño/template de la Ficha
   (`ficha_reserva_cliente.html`) parametrizado `modo='cotizacion'`: muestra solo el acordeón
   **Servicios** (líneas desde el `payload` de la propuesta: servicio_id→nombre/precio, descuento,
   total) + botón **Aprobar**; sin Tips/Comanda. `noindex`.
3. **Endpoint Aprobar** `aprobar_cotizacion(request, token)` (POST): resuelve la propuesta, llama a
   `crear_reserva_desde_propuesta`, y **redirige a la Ficha** de la reserva creada
   (`token_para_reserva(reserva_id)`). Idempotente (si ya creada, redirige igual).
4. **Helpers de URL**: `url_cotizacion(propuesta_id)` (para que el cajón arme el link).
5. **OpenGraph** en cotización y Ficha (title/description/image del río) para la tarjeta de preview
   de WhatsApp.
6. **Luna (prompt)**: al cerrar los servicios, preguntar "¿Te envío la cotización?"; con el sí,
   confirmar carrito → propuesta. (Sin auto-enviar; queda como borrador en el cajón.)
7. **Retirar** el cotizador de texto viejo (`cotizacion_reserva_view` / `cotizacion.html`) cuando
   esto esté en prod (queda obsoleto).

### B. aremko-cli (agente aremko-cli)
> Lado Django de la cotización + Aprobar YA está en prod y validado (oferta→propuesta→cotización→
> Aprobar→Ficha, con descuento de pack consistente en los 4). Falta el lado del cajón:
1. El cajón muestra, cuando hay una `PropuestaReserva` lista (estado `pendiente`), un **borrador
   con el link de cotización** para que Deborah lo revise y envíe (hoy muestra el banner "Crear
   reserva"). El link se obtiene con `ventas.views.ficha_reserva_view.url_cotizacion(propuesta_id)`
   → `https://www.aremko.cl/ventas/propuesta/<token-firmado>/` (token = `signing.dumps(propuesta_id)`,
   no adivinable). Interino: hay link clickeable en el admin de `PropuestaReserva` ("🌙 Cotización").
2. Tras el Aprobar del cliente (la reserva ya se creó sola), el banner pasa a **"Revisar y enviar
   Ficha"** (mostrar resumen de la reserva creada + botón para enviar el link de la Ficha). El link
   de la Ficha: `url_ficha_reserva(reserva_id)` → `.../ventas/reserva/<token>/`. Esto es la Fase 2
   del proyecto (link de Ficha al cajón).
3. **Línea de descuento en el banner:** ahora `preparar_reserva` deja el total de la propuesta YA
   con el descuento del pack (ej. tina+masaje queda en $110.000, no $130.000) y agrega al
   `propuesta.resumen_texto` una línea `Descuento pack = -$X`. El banner muestra el TOTAL correcto
   pero las líneas estructuradas (tina + masaje) suman el bruto → conviene mostrar la **línea de
   descuento explícita** (leer `resumen_texto` o exponer el descuento) para que cuadre. (Y el caso
   Ritual: la línea cruda `Descuento_Servicios · 30000p` → mostrarla limpia "Descuento · −$30.000".)

## Reuso confirmado (no reinventar)
- `crear_reserva` ya es **idempotente** y consume `propuesta_id` → `PropuestaReserva` tiene
  `payload`, `estado`, `reserva_id`, `expires_at`, `esta_vigente()`.
- Diseño/template de la **Ficha** (Fase 1) → la cotización es la misma página en `modo='cotizacion'`.
- `token_para_reserva` / patrón `signing` ya en `ficha_reserva_view.py`.

## Estado
- **Django**: ✅ HECHO y validado en prod — cotización `propuesta/<token>/` + Aprobar (reusa
  `crear_reserva`), descuento de pack consistente (propuesta/cotización/reserva, vía
  `PackDescuentoService.construir_cart`), "Pausa junto al río", #3 (no filtra `propuesta_id` ni
  "confirmada"). Pendiente menor Django: pregunta de consentimiento en prompt de Luna ("¿te envío
  la cotización?") + retirar el cotizador de texto viejo (`cotizacion_reserva_view`).
- **aremko-cli**: ⬜ PENDIENTE (B1–B3) — cajón con link de cotización + banner "Revisar y enviar
  Ficha" + línea de descuento explícita.
