# Informe para el agente aremko-cli — Leads de /refugio/ y reporte real de campañas

**Fecha:** 2026-06-01 · **Tipo:** Diagnóstico (solo lectura) + especificación para el reporting
**Solicitado por:** Jorge · **Para:** agente aremko-cli (sistema de brief/reportes)

---

## 1. Resumen ejecutivo

El cliente reportó "12 leads en Meta pero 0 correos recibidos" del formulario de la landing `/refugio/`. Tras el diagnóstico:

- **El formulario funciona, guarda en BD y envía correos.** No hay leads perdidos.
- **En la BD hay solo 3 sumisiones reales** (no 12). Fuente: tabla `ventas_refugiolead`.
- **Los "~12 leads" de Meta están inflados:** el evento `Lead` del Pixel se dispara también en **cada reserva del checkout** (Pixel + CAPI), no solo en el formulario de refugio. El reporte actual cuenta ese evento como "leads de campaña".
- **Los correos sí se enviaron y entregaron**, pero el remitente (`comunicaciones@aremko.cl`, buzón inexistente/en lista de rebotes) hace que **caigan en Spam/Promociones** de Gmail.

**Acción urgente de negocio:** contactar a **Patricia** (lead real de campaña del 28-may, ver §2).

---

## 2. Datos reales de leads (tabla `ventas_refugiolead`) — TOTAL: 3

| Fecha | Nombre | Email | Teléfono | Ciudad | utm_source | utm_campaign | Tipo |
|---|---|---|---|---|---|---|---|
| 2026-05-28 | **Patricia** | phermosillas.9@gmail.com | +56 9 9817 7119 | Santiago | **facebook** | **refugio_lanzamiento_junio** | ✅ Lead real de campaña (Meta) |
| 2026-06-01 | Deborah Gonzalez | deborahscott80@hotmail.com | +56 9 8447 2411 | San Antonio | (sin UTM) | (sin UTM) | Lead reciente (origen directo/no atribuido) |
| 2026-05-29 | jorge aguilera | ecolonco@gmail.com | +56 9 5865 5810 | Puerto Varas | (sin UTM) | (sin UTM) | ⚠️ Prueba interna (excluir del reporte) |

> **Leads reales de marketing = 1–2** (Patricia con atribución Meta; Deborah sin UTM). La prueba interna (jorge/ecolonco) debe excluirse del conteo de campaña.

---

## 3. Causa raíz del número inflado de Meta (lo que el reporting debe corregir)

El evento **`Lead` del Meta Pixel se dispara en 3 lugares**, no solo en el formulario:

| Lugar | Archivo | Cuándo dispara |
|---|---|---|
| Formulario Refugio | `ventas/templates/ventas/refugio_landing.html:527` — `fbq('track','Lead',{content_category:'refugio'})` | Solo en envío exitoso del formulario |
| Checkout (Pixel) | `ventas/templates/ventas/checkout.html:858` — `fbq('track','Lead', …)` | En **cada** reserva creada |
| Checkout (CAPI server-side) | `ventas/services/meta_capi_service.py:214` | En **cada** `PendingReservation` |

El reporter de Meta (`ventas/services/meta_reporter.py:485`) cuenta el action `offsite_conversion.fb_pixel_lead` (y `lead`, `leadgen.other`) como "leads". **Ese número mezcla los leads del formulario con los eventos Lead del checkout** → por eso aparece ~12 cuando el formulario real tuvo 3.

---

## 4. Fuentes correctas para contar "leads de campaña" (recomendación clave)

| Fuente | ¿Limpia para leads de refugio? | Nota |
|---|---|---|
| **`ventas_refugiolead` (BD)** | ✅ **Autoritativa** | Tiene los datos de contacto + UTM. Filtrar por `utm_*` y excluir emails de prueba. ES la fuente de verdad. |
| **GA4 evento `refugio_form_submit`** | ✅ Limpio | Se dispara solo en `data.success` (`refugio_landing.html:514`). Debería ≈ conteo de la BD. Ya está en `custom_events` del brief. |
| **Google Ads conversión "Refugio Form Submit"** | ✅ Limpio | `AW-18196625156/2z2aCNrR4rUcEITu6eRD`, dispara solo en éxito del formulario. |
| **Meta `fb_pixel_lead` / `lead`** | ❌ **Contaminado** | Incluye los Lead del checkout (Pixel+CAPI). NO usar como "leads de formulario". |

**Recomendación para el brief/reporte:**
1. Para "**Leads del formulario Refugio**" usar el **conteo de la BD `RefugioLead`** (o el evento GA4 `refugio_form_submit`), **no** el `fb_pixel_lead` de Meta.
2. El número de Meta debe etiquetarse como "**Eventos Lead (mixto: formulario + reservas)**", no como "leads de campaña", para no confundir.
3. Calcular **CPL real** = inversión de la campaña ÷ leads reales de la BD (no ÷ eventos Lead de Meta), para no subestimar el costo por lead.
4. Mostrar la **lista real de leads con su atribución UTM** (como la tabla del §2) — es lo más accionable para el cliente.
5. *(Opcional, requiere cambio de código en sitio)* separar el evento del formulario refugio del Lead del checkout (renombrar a un evento propio o usar el `content_category:'refugio'` para segmentar), para que la optimización "Lead" de la campaña Refugio en Meta no se contamine con reservas.

---

## 5. Estado del email de notificación (contexto para el reporte)

- El handler (`ventas/views/public_views.py:749` `refugio_submit_view`) **envía** notificación al equipo + confirmación al lead **desde el día 1** (commit `d5494e2`, 2026-05-27).
- Verificado en SendGrid: los recientes (Patricia fuera de retención; Deborah 06-01; prueba 05-29) **se entregaron** a `aremkospa@gmail.com` y `ventas@aremko.cl`. El `not_delivered` es solo a `comunicaciones@aremko.cl` (buzón inexistente).
- Problema de visibilidad: remitente `comunicaciones@aremko.cl` (en lista de rebotes) → **Spam/Promociones**. Además `fail_silently=True` (`public_views.py:856,874`) oculta fallos.
- *(Fix propuesto aparte, no implementado: cambiar remitente a dirección verificada, quitar `comunicaciones@aremko.cl` de destinatarios, quitar `fail_silently`, agregar flag `notificado`.)*

---

## 6. Qué debería mostrar el reporte de campañas (Meta Ads + Google Ads) para ser "real"

1. **Por canal (Meta vs Google):** inversión, impresiones, clics, CTR, LPV.
2. **Leads reales** (de la BD `RefugioLead` / GA4 `refugio_form_submit`), **no** del `fb_pixel_lead` de Meta.
3. **CPL real** por canal = inversión ÷ leads reales.
4. **Lista de leads** con nombre, contacto, fecha y atribución UTM (excluir pruebas internas).
5. **Embudo Refugio:** `refugio_view` → `refugio_form_submit` (si view sube y submit no → fricción en formulario/precio).
6. Nota de **conciliación**: explicar la diferencia entre "Eventos Lead de Meta" (mixto) y "Leads de formulario reales" para que el cliente entienda el número.

---

## Apéndice — referencias de código
- Modelo/tabla: `ventas/models.py:7436` `RefugioLead` → `ventas_refugiolead`
- Handler: `ventas/views/public_views.py:749` `refugio_submit_view`
- Pixel Lead (form): `refugio_landing.html:527` · (checkout): `checkout.html:858` · (CAPI): `meta_capi_service.py:214`
- Reporter Meta (cuenta leads): `ventas/services/meta_reporter.py:485`
- GA4 evento limpio: `refugio_landing.html:514` `refugio_form_submit`
- Google Ads conversión: `google_ads_reporter.py:56-57` (`AW-18196625156/2z2aCNrR4rUcEITu6eRD`)
