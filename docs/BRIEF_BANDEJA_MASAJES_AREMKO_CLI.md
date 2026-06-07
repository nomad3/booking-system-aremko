# Brief — Bandeja de salida "Conexión-Masajes" (aremko-cli)

> Handoff para el agente que implementa la UI en **aremko-cli (Go)**.
> El lado Django (booking-system-aremko) ya está implementado, desplegado y validado en producción.

## 1. Objetivo
Construir en aremko-cli una pantalla **"Bandeja de salida – Masajes"** donde Debora, Angélica o Jorge puedan **revisar, editar y enviar** (uno por uno) los emails de seguimiento de bienestar post-masaje. Hoy esos emails **no se envían solos**: quedan encolados en Django y esperan aprobación humana desde esta bandeja.

**Reparto de responsabilidades:**
- **Django** (booking-system-aremko) = fuente de verdad + **motor de envío** (SendGrid, branding "Aremko Spa Boutique", botón de baja, respeto al opt-out). Ya está desplegado y probado.
- **aremko-cli (tú)** = **UI**: listar, ver preview, editar, botón Enviar, botón Cancelar.

No tienes que enviar correos ni renderizar HTML: solo consumes la API y muestras lo que Django entrega.

## 2. Conexión y autenticación
- **Base URL:** `https://www.aremko.cl`
- **Auth:** header `X-API-Key: <LUNA_API_KEY>` en **todas** las llamadas (mismo secreto que ya usas para los endpoints de WhatsApp). Sin header válido → `401`.
- Producción fuerza HTTPS. Content-Type de respuestas: `application/json` (salvo el preview, que es `text/html`).

## 3. Endpoints

### 3.1 Listar la bandeja
```
GET /api/masaje/outbox/?incluir_programados=1&limit=200
```
Query params (opcionales): `incluir_programados` (`1`/`0`, default `1`), `limit` (default 200, máx 500).

**Respuesta 200:**
```json
{
  "ok": true,
  "para_enviar": [
    {
      "id": 23,
      "tipo_email": "resumen_bienestar",
      "tipo_label": "Resumen de bienestar (post-masaje)",
      "estado": "pendiente",
      "destinatario_nombre": "Eliana Carrasco",
      "destinatario_email": "eliana.carrasco1@gmail.com",
      "fecha_programada": "2026-06-06T13:00:00+00:00",
      "fecha_envio": null,
      "asunto": "Tu resumen de bienestar en Aremko Spa Boutique 🌿",
      "cuerpo": "Hola Eliana,\n\nQueremos compartirte...",
      "reserva_id": 5945,
      "enviado_por": "",
      "editado_por": "",
      "editado_at": null,
      "error_log": "",
      "preview_html": "<div style=...> ...HTML final del email... </div>"
    }
  ],
  "programados": [ { "...igual pero SIN preview_html..." } ],
  "total_para_enviar": 3,
  "total_programados": 14
}
```
- **`para_enviar`** = vencidos (`fecha_programada <= ahora`), **accionables ahora**. Incluyen `preview_html` (HTML final listo para mostrar en iframe).
- **`programados`** = futuros (`fecha_programada > ahora`), informativos. **No** traen `preview_html` (pídelo con el endpoint de preview si hace falta).

### 3.2 Preview HTML (de cualquier id)
```
GET /api/masaje/outbox/<id>/preview/
```
Devuelve `text/html` con el email **tal cual lo recibirá el cliente** (header, cuerpo, botón "Reservar mi masaje", botón "No recibir más comunicaciones", footer). Úsalo en un iframe/sandbox. Refleja el `cuerpo` actual (post-edición).

### 3.3 Editar asunto/cuerpo
```
PATCH /api/masaje/outbox/<id>/
Body JSON: { "asunto": "...", "cuerpo": "...", "operador": "debora" }
```
- Puedes mandar `asunto`, `cuerpo`, o ambos. `operador` para auditoría.
- El `cuerpo` es **texto plano** (Django lo envuelve en el HTML de marca al enviar; los saltos de línea `\n` se respetan). No mandes HTML.
- **Respuesta 200:** `{ "ok": true, "item": { ...con preview_html actualizado... } }`
- Solo se puede editar si `estado == "pendiente"` (si no → `409`).

### 3.4 Enviar ahora
```
POST /api/masaje/outbox/<id>/send/
Body JSON: { "operador": "jorge" }
```
- **200** → `{ "ok": true, "estado": "enviado", "error": null, "item": {...} }`
- **422** → `{ "ok": false, "estado": "error"|"cancelado", "error": "...", "item": {...} }`
  - Caso especial: si el cliente **se dio de baja**, devuelve 422 y deja el seguimiento en `cancelado` (no se envía). Muéstralo como "Cliente dado de baja, no se envió".
- Solo si `estado == "pendiente"` (si no → `409`). Es **final**: una vez `enviado`, no se puede reenviar ni editar.

### 3.5 Cancelar
```
POST /api/masaje/outbox/<id>/cancel/
Body JSON: { "operador": "angelica" }
```
- **200** → `{ "ok": true, "item": {...} }` (queda `estado: "cancelado"`).
- Solo si `estado == "pendiente"` (si no → `409`).

## 4. Catálogos / valores

**`tipo_email`** (con su `tipo_label`):
| tipo_email | tipo_label |
|---|---|
| `gracias_visita` | Gracias por la visita |
| `resumen_bienestar` | Resumen de bienestar (post-masaje) |
| `seguimiento_7d` | Seguimiento 7 días |
| `recomendacion_30d` | Recomendación 30 días |
| `reactivacion_60d` | Reactivación 60 días |
| `reactivacion_90d` | Reactivación 90 días |

**`estado`:** `pendiente` · `enviado` · `error` · `cancelado`

**`operador`:** `"debora"` · `"angelica"` · `"jorge"` (string libre; mándalo siempre — alimenta `enviado_por`/`editado_por`).

**Códigos HTTP:** `200` OK · `400` body inválido / nada que editar · `401` API key faltante/incorrecta · `404` id inexistente · `409` el seguimiento ya no está `pendiente` · `422` el envío falló o el cliente está dado de baja.

## 5. Requisitos de UI

Pantalla **"Bandeja de salida – Masajes"**:
- **Sección "Para enviar" (vencidos)**: tabla/lista con `destinatario_nombre`, `destinatario_email`, `tipo_label`, `fecha_programada` (formatear a hora de Chile, `America/Santiago`), `estado`.
  - Por fila: **Ver** (abre el `preview_html` en iframe), **Editar** (formulario asunto + cuerpo), **Enviar** (confirmación → POST send), **Cancelar**.
  - Tras editar, refrescar el preview con lo que devuelve el PATCH.
  - Tras enviar/cancelar, sacar la fila de "Para enviar" o marcar su nuevo estado.
- **Sección "Programados" (futuros)**: solo lectura (fecha + destinatario + tipo); útil para visibilidad. Botón "ver preview" opcional (llama al endpoint).
- Mostrar auditoría cuando exista: `enviado_por`, `editado_por` + `editado_at`.
- Manejo de errores: mapear `409`/`422`/`401` a mensajes claros (ej. 422 baja → "El cliente se dio de baja; no se envió").

## 6. Notas
- **Volumen bajo** (unas pocas por día). No hace falta paginación compleja ni websockets; refresca al entrar y tras cada acción.
- **Privacidad:** Debora/Angélica/Jorge **sí** pueden ver el email del cliente en esta bandeja (son coordinación, no masajistas).
- El `cuerpo` editable es texto; el formato de marca (logo, botones, footer, botón de baja) lo agrega Django automáticamente al enviar y en el preview. No dupliques branding.
- El `gracias_visita` se envía **sin** botón "Reservar" (los demás sí lo llevan); eso ya viene resuelto en el `preview_html`.

## 6.b — Cómo se arma la lista (criterios)

- **Qué cuenta como "masaje":** `ReservaServicio` cuyo `servicio.tipo_servicio == 'masaje'`. Al guardar una reserva con una línea de masaje, un signal genera los `ParticipanteMasajeReserva` (comprador + acompañantes según `cantidad_personas`).
- **Quién crea los seguimientos:**
  - Al **completar la ficha de bienestar** de un participante → se programan los de la cadencia.
  - Al **guardar el resumen** de la masajista → se programa `resumen_bienestar`.
- **Ventana temporal por tipo (offset desde que se LLENA la ficha, NO desde la fecha del masaje):** `gracias_visita` +24 h · `seguimiento_7d` +7 d · `recomendacion_30d` +30 d · `reactivacion_60d` +60 d · `reactivacion_90d` +90 d · `resumen_bienestar` inmediato.
- **Gating por consentimiento:** los comerciales (7d/30d/60d/90d) solo se crean si la ficha tiene `consentimiento_marketing=True`. `gracias_visita` y `resumen_bienestar` son transaccionales (siempre).
- **Estado:** la bandeja solo lista `estado='pendiente'`. `para_enviar` = `fecha_programada <= ahora`; `programados` = futuros.
- **Filtro geográfico:** ⚠️ HOY NO existe. La lista no filtra por región/ciudad — por eso pueden aparecer clientes de cualquier zona (ej. Santiago). El filtrado/`badge` lo decide aremko-cli con el campo `region` (ver abajo). Un filtro server-side por región es una decisión pendiente a coordinar.
- **Opt-out:** el `send` respeta la baja de email (ClientPreferences). No hay exclusión por región.

## 6.c — Campos enriquecidos (v2, ya en el JSON de cada item)

Presentes tanto en `para_enviar` como en `programados`:

| Campo | Tipo | Descripción |
|---|---|---|
| `destinatario_telefono` | string | Teléfono del cliente, normalizado E.164 (ej. `+569XXXXXXXX`). Para wa.me, quitar el `+`. |
| `ciudad` | string\|null | Ciudad canónica (`Cliente.ciudad_normalizada.nombre_canonico`) o `null` si sin clasificar. |
| `region` | string | Categoría geográfica: `sur` \| `nacional` \| `extranjero` \| `sin_clasificar`. |
| `region_label` | string | Etiqueta legible (`Sur`, `Resto de Chile`, `Extranjero`, `Sin clasificar`). |
| `apto_visita` | bool | `true` solo si `region == 'sur'` (regla inicial, ajustable). |
| `servicio` | string\|null | Nombre del masaje recibido (de la línea de la reserva). |
| `fecha_visita` | string(date)\|null | Fecha del masaje (`fecha_agendamiento` de la línea). |
| `num_visitas` | int | Nº de reservas del cliente. |
| `cliente_nuevo` | bool | `true` si `num_visitas <= 1`. |

**Taxonomía geográfica (`region`):** misma que la bandeja WhatsApp.
- `sur` = Sur, ≤120 km de Puerto Varas → **apto visita**.
- `nacional` = Resto de Chile.
- `extranjero` = fuera de Chile.
- `sin_clasificar` = sin ciudad/comuna reconocida (default). Se puebla con el comando `normalizar_ciudades_clientes` (texto libre `ciudad` + `comuna` → `ciudad_normalizada` + `region_geografica`). Editable a mano desde la bandeja WhatsApp (queda `ciudad_normalizada_manual=True`).

El catálogo de `ciudad` (canónicas) vive en el modelo `Ciudad` (admin: aliases + región). No es enum fijo; se consulta en BD.

## 7. Referencia (lado Django, ya implementado)
- Vistas API: `ventas/views/masaje_outbox_api_views.py`
- Rutas: `aremko_project/urls.py` (`/api/masaje/outbox/...`)
- Modelo: `SeguimientoBienestarMasaje` en `ventas/models.py` (migración `0124` para auditoría)
- Auth: helper `_check_luna_key` (valida `settings.LUNA_API_KEY`)
- Render del email: `ventas/services/masaje_seguimiento_service.py` (`enviar_seguimiento`, `construir_html_preview`)
