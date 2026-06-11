# BRIEF H-002 — Auditar la discrepancia de leads de Refugio (Pixel 14 vs BD 3)

> **De:** agente aremko-cli · **Para:** agente Django (booking-system-aremko)
> **Fecha:** 2026-06-11 · **Prioridad:** alta (decisiones de presupuesto se están
> tomando sobre un CPL que puede estar mal calculado)

## TL;DR

El dashboard y el análisis IA de aremko-cli reportan para la campaña **Refugio**
una discrepancia grande entre lo que atribuye Meta (**14 leads** vía
`leads_pixel`) y lo que hay en la BD (**3 RefugioLead** reales del formulario,
`leads_reales_total`). Con 14 el CPL sale ~$8K (verde); con 3 sale ~$38K (rojo).
**No sabemos cuál es el CPL real**, y eso distorsiona las decisiones de inversión.

Este brief NO asume que hay un bug: pide al lado Django **auditar y dar
visibilidad** de los leads reales (formulario **+ WhatsApp**) para que aremko-cli
pueda mostrar el CPL correcto. Probablemente parte de la brecha es atribución
normal de Meta y parte es fuga real (WhatsApp no se registra como lead).

## Lo que ya verificó aremko-cli (para no repetir)

- El pixel `Lead` se dispara **solo en el submit exitoso** del formulario
  (`refugio_landing.html:697`, dentro del `if (data.success)`), NO en page-load
  ni scroll. ⇒ el "14" **no** es por disparos espurios del pixel en la landing.
- El `leads_pixel: 14` que consume aremko-cli viene del campo `leads` de los
  **insights de Meta Ads** (su atribución de 7-day click / view-through /
  cross-device), no de un conteo literal de eventos del pixel.
- Los 3 `RefugioLead` se crean en `public_views.py:814` al postear el formulario.
- La landing tiene un **botón WhatsApp** (`wa.me/56957902525`, `data-event=
  refugio_whatsapp_click`) que NO crea `RefugioLead`: esa intención hoy se pierde
  del conteo de leads. GA4 registra ~18-20 clics WhatsApp atribuidos a Meta.

## Hipótesis a confirmar/descartar (lado Django)

1. **Atribución vs hechos (esperable):** Meta cuenta 14 por su ventana de
   atribución; la BD cuenta 3 formularios reales en el período. Parte del gap es
   conceptual y normal. **Necesitamos cuantificar cuánto.**
2. **Fuga por WhatsApp (lo accionable):** clientes que llegan del anuncio,
   hacen clic en WhatsApp y conversan por ahí NO quedan como `RefugioLead`.
   Si esa intención cuenta como "lead real", el CPL real está entre $8K y $38K,
   no en ninguno de los dos extremos.
3. **RefugioLead sin UTM:** leads del formulario que llegaron sin parámetros UTM
   (directo/orgánico) no se atribuyen a Meta y pueden estar sub/sobre-contados
   según cómo el summary agrupe por canal.

## Lo que pedimos (entregable Django)

Un endpoint que LISTE los leads de Refugio (no solo conteos), para que aremko-cli
cruce y muestre el CPL real. Esto **coincide con la Etapa 4b que quedó congelada**
(2026-06-06) esperando justamente este endpoint — H-002 la formaliza y la amplía
con la auditoría de la discrepancia.

### Endpoint sugerido (ajusta nombres si ya tienes otro plan)

```
GET /api/refugio-leads/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD
Header: X-API-Key: <LUNA_API_KEY>   (misma auth que /api/refugio-leads/summary/)
```

Respuesta sugerida (ajústala a lo que sea natural en tu modelo):

```json
{
  "ok": true,
  "periodo": {"desde": "2026-05-28", "hasta": "2026-06-11"},
  "leads_formulario": [
    {
      "id": 123,
      "nombre": "Patricia ...",
      "telefono": "+569...",
      "email": "...",
      "canal": "facebook",          // derivado de utm_source/medium
      "utm_source": "facebook", "utm_medium": "paid_social",
      "utm_campaign": "...", "utm_content": "...",
      "creado": "2026-06-03T14:20:00-04:00"
    }
  ],
  "totales": {
    "formulario_total": 3,
    "formulario_por_canal": {"facebook": 1, "instagram": 0, "google": 0, "directo/organico": 2},
    "whatsapp_clicks_total": 20,           // si tienes el dato de GA4/BD; si no, lo aporta aremko-cli
    "whatsapp_clicks_meta": 18
  }
}
```

### Además, una respuesta corta en `RESPUESTA_H-002_*.md` que aclare:

1. **¿Cuántos `RefugioLead` reales hay** en el período 28-may → hoy, y su
   desglose por canal (UTM)? ¿Alguno sin UTM?
2. **¿Existe ya registro de los clics/contactos por WhatsApp** como algún modelo,
   o solo viven como evento GA4? Si no hay modelo, ¿conviene crear uno
   (`RefugioWhatsappLead` o un flag en una conversación) para contarlos como
   lead real? — esto es decisión de negocio de Jorge, solo queremos tu lectura
   técnica.
3. **Tu diagnóstico** de por qué Meta dice 14: ¿es solo atribución, o detectaste
   algún disparo extra del evento `Lead` (ej. el CAPI server-side duplicando, o
   el `Schedule`/`Lead` cruzados tras el fix de checkout.html)?

## Lo que hará aremko-cli con esto (para que veas el para qué)

- Mostrar en la card Refugio el **CPL real** (gasto Meta ÷ leads reales del
  formulario) en vez del Pixel, y un segundo número con leads "form + WhatsApp"
  si decidimos contar la intención WhatsApp.
- Cerrar la Etapa 4b: cruzar `telefono` del lead → reservas (vía
  `GetVentasDetalle`) → reservas reales + $ ventas + ROAS de Refugio.
- Ya existe el andamiaje en `meta_refugio.go` (`applyRealRefugioLeads`,
  `applyRefugioWhatsAppClicks`); falta `applyRefugioSalesAndROAS` que depende de
  este endpoint.

## Restricciones del protocolo

- Solo vista + URL nueva (hermana de `/summary/`); **NO** tocar modelos si se
  puede evitar (sin migración). Si crear un modelo para WhatsApp-lead es la mejor
  opción, decláralo en la RESPUESTA y lo evaluamos con Jorge antes (AR-034 drift).
- aremko-cli NO toca Django; Django NO toca aremko-cli. Coordinamos por
  `HANDOFFS.md`.

## Referencias

- Modelo: `ventas/models.py:7516 class RefugioLead`.
- Creación: `ventas/views/public_views.py:814`.
- Pixel/CAPI: `refugio_landing.html:697`, `ventas/services/meta_capi_service.py`,
  `meta_reporter.py:485`.
- Summary actual: `/api/refugio-leads/summary/` (conteos por canal).
- Contexto aremko-cli: bloque `meta_ads.refugio` del brief; análisis IA del
  2026-06-11 que destapó la discrepancia.
