# BRIEF H-042 — Cotización EDITABLE + botón CERRAR el cajón (aremko-cli)

> **De:** agente Django (`~/dev/booking-system-aremko`)
> **Para:** agente aremko-cli (`~/Documents/GitHub/aremko-cli.nosync`)
> **Estado Django:** ✅ HECHO y **vivo en prod** (commits `0bca679` + el de este brief). La API está lista; falta SOLO el front.

---

## 1. Por qué (pedido de Jorge, 2026-06-28)

Hoy Luna trabaja en **modo supervisado** (`WhatsAppAgentConfig.modo = 'borrador'`): arma la
cotización y queda en el **cajón** para que Deborah la revise; **nada se auto-envía al cliente**.
El plan de Jorge es por fases: **(1)** Deborah revisa y **corrige** la cotización antes de
enviarla; **(2)** cuando veamos que Luna la arma 100% bien, flipear `modo` y que pase directo.

**El problema:** hasta ahora la `PropuestaReserva` era **inmutable**. Si Luna se equivocaba
(caso real: duplicó productos → 2 tablas + 5 jugos, cotización inflada ~$45k), Deborah solo
podía descartar y rehacer. Ahora la API permite **corregir** y **cerrar** el borrador.

Jorge pidió 2 cosas concretas para el cajón:
- **(A)** Poder **corregir** la cotización (cambiar cantidades, quitar líneas) antes de enviar.
- **(B)** Poder **cerrar** el borrador de cotización desde la ventana de la conversación para
  seguir con el proceso de venta.

---

## 2. Qué ya está LISTO en Django (vivo en prod)

### 2.1 El cajón ahora trae los IDs (necesarios para editar)
El endpoint que ya consumís para el cajón —`GET /api/inbox/conversation/` y su gemelo
`GET /api/whatsapp/conversation/`— devuelve `propuesta_reserva.servicios[]`. **Ahora cada línea
incluye su id** (cambio aditivo, no rompe nada):

```jsonc
"propuesta_reserva": {
  "propuesta_id": "uuid-string",
  "url_cotizacion": "https://...",
  "resumen": "…",
  "total": 118000,
  "servicios": [
    // SERVICIO (tina/masaje/cabaña): tiene servicio_id + fecha/hora
    { "servicio_id": 12, "servicio_nombre": "Tina Calbuco", "fecha": "2026-06-29",
      "hora": "14:30", "cantidad_personas": 3, "subtotal": 75000 },
    // PRODUCTO (tabla/jugo): tiene producto_id, fecha/hora = null, es_producto = true.
    // OJO: para productos, la cantidad viene en `cantidad_personas`.
    { "producto_id": 5, "servicio_nombre": "Tabla Mixta de Quesos y Jamones",
      "fecha": null, "hora": null, "cantidad_personas": 1, "subtotal": 36000,
      "es_producto": true }
  ]
}
```

### 2.2 Endpoint para CORREGIR la cotización
```
POST /api/luna/reservas/editar/
Header: X-API-Key: <misma key que usás para los demás /api/luna/*>
Body:
{
  "propuesta_id": "uuid-string",
  "servicios": [                                  // lista COMPLETA y FINAL tras la edición
    { "servicio_id": 12, "fecha": "2026-06-29", "hora": "14:30", "cantidad_personas": 3 }
  ],
  "productos": [                                   // lista COMPLETA y FINAL (opcional)
    { "producto_id": 5, "cantidad": 1 }
  ]
}
```
**Semántica = REEMPLAZO TOTAL** (no es un PATCH por línea). Mandás cómo queda la cotización
COMPLETA después de editar. Para:
- **cambiar cantidad** → mandá la línea con la nueva `cantidad_personas`/`cantidad`.
- **quitar una línea** → omitila de la lista.
- Django **re-lee los precios del catálogo** y recalcula total + descuento de pack + resumen
  con la MISMA lógica que al crear la propuesta (`recalcular_propuesta`, fuente única). Es decir:
  **vos NO mandás precios ni totales**, solo ids + cantidades; el total te lo devuelve Django.

Respuesta:
```jsonc
{ "success": true, "propuesta_id": "...", "resumen_texto": "…",
  "total": 118000, "servicios_count": 1, "productos_count": 1 }
```
Errores (HTTP 400): `no_editable` (la propuesta ya no está pendiente), `expirada`,
`validation_error` (ej. lista de servicios vacía — debe quedar ≥1 servicio), `service_not_found`,
`product_not_found`.

> Tras editar, **volvé a leer la conversación** (`/api/.../conversation/`) y el cajón se
> refresca solo: cambia `payload`, `total` y `resumen` en la MISMA propuesta (mismo `propuesta_id`).
> No se crea una propuesta nueva. El "Aprobar" del cliente y `crear_reserva` consumen el payload
> editado → la corrección llega hasta la `VentaReserva`.

### 2.3 Endpoint para CERRAR/descartar el borrador
```
POST /api/luna/reservas/descartar/
Header: X-API-Key
Body: { "propuesta_id": "uuid-string" }
→ { "success": true, "propuesta_id": "...", "estado": "descartada" }
```
Marca la propuesta como `descartada` → deja de ser "vigente" → **desaparece del cajón** en la
próxima lectura de la conversación. La conversación sigue normal. Error 400 `no_descartable` si
no existe o no está pendiente.

---

## 3. Tareas aremko-cli

El componente del cajón ya existe: **`CotizacionCajon.tsx`** (el de H-039/H-040, cableado en
WhatsApp + Instagram/Messenger). Sobre ese:

### (A) Cotización editable
- Modo "editar" en el cajón: por cada línea, permitir **cambiar la cantidad** (stepper/input) y
  **quitar la línea** (✕). Para servicios la cantidad es `cantidad_personas`; para productos
  (`es_producto:true`) la cantidad es `cantidad_personas` también (mapealo a `cantidad` al enviar).
- Al **Guardar**, construir las listas COMPLETAS desde el estado del cajón y hacer
  `POST /api/luna/reservas/editar/`. Luego refrescar la conversación para repintar el cajón con el
  total que devolvió Django (**no calcules el total en el front** — usá el de la respuesta / la
  relectura).
- No permitir guardar con 0 servicios (Django igual lo rechaza con `validation_error`).
- Edición mínima viable: **cantidad + quitar línea**. NO hace falta editar fecha/hora ni precios
  en esta primera versión (precios siempre del catálogo).

### (B) Botón Cerrar
- Botón **"Cerrar"** (o ✕) en el cajón de cotización → `POST /api/luna/reservas/descartar/` →
  al éxito, ocultar el cajón y refrescar. (Distinto del ✕ del banner verde "Reserva creada" de
  H-039, que es solo cosmético/localStorage; este sí descarta la propuesta en el backend.)

### Capa Go
Los endpoints de conversación son passthrough crudo (H-039). Los **dos POST nuevos**
(`/editar/`, `/descartar/`) hay que asegurarse de que el proxy Go los exponga/passthrough con el
header `X-API-Key` y **acepte el 200** de Django (ver el patrón de "Go acepta 2xx" — si el proxy
solo aceptaba 200/201, ojo que estos devuelven **200**).

---

## 4. Criterios de aceptación (prueba viva de Jorge)
1. En un cajón de cotización con líneas duplicadas/erradas, Deborah ajusta cantidades / quita una
   línea → Guardar → el cajón muestra el **total corregido** y el `resumen` nuevo.
2. El link de cotización que se envía al cliente y el "Aprobar" reflejan la versión **editada**
   (la `VentaReserva` creada queda con los montos corregidos).
3. Botón **Cerrar** → el cajón desaparece y la conversación sigue; al recargar, no reaparece.
4. `tsc` 0 errores + `next build` OK.

## 5. Gotchas aremko-cli
- **Deploy NO es automático** (`feedback_aremko_cli_deploy_manual`): tras pushear, pedir **Manual
  Deploy** en Render; si el bug persiste con el mismo síntoma, sospechar deploy no-live.
- Coordinar: la API Django ya está en prod, así que podés integrar de una.
- Actualizá `types.ts` si agregás `servicio_id`/`producto_id` al tipo de la línea del cajón.

## 6. Estado al cerrar (para HANDOFFS.md)
- **Django:** ✅ vivo en prod. `recalcular_propuesta` (fuente única) + `editar_propuesta` +
  `cancelar_propuesta` (fix 'descartada') + endpoints `editar/`+`descartar/` + IDs en
  `_propuesta_reserva`. Commits `0bca679` (+ este brief).
- **aremko-cli:** ⬜ pendiente (A) editar + (B) cerrar.
