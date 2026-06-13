# RESPUESTA H-004 — Endpoint editar nombre del cliente: LISTO

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-004_editar_nombre_cliente.md`

## TL;DR

Endpoint implementado **tal cual el contrato propuesto** (commit en `whatsapp_api_views.py`
+ `urls.py`), sin migración, en producción. Confirmado que el relleno automático
NO pisa la corrección manual.

## Contrato final (sin cambios respecto al brief)

```
POST /api/whatsapp/conversations/<phone>/editar-nombre/
Header: X-API-Key: <LUNA_API_KEY>
Body JSON: { "nombre": "Nombre Real" }
```

**Respuestas:**
- `200` → `{ "ok": true, "cliente_id": <int>, "cliente_nombre": "<nuevo>" }`
- `400` → `{ "ok": false, "error": "nombre requerido" }` (vacío o solo espacios)
- `400` → `{ "ok": false, "error": "phone requerido" }` (phone vacío)
- `401` → `{ "error": "No autorizado..." }` (sin/mal X-API-Key)
- `404` → `{ "ok": false, "error": "No se pudo resolver el cliente por teléfono" }`
- `405` → método ≠ POST

## Comportamiento

1. `_match_or_create_cliente(phone)` resuelve la ficha por teléfono (reusado, igual
   que el resto del flujo WhatsApp).
2. `cliente.nombre = nombre.strip()[:100]` (trunca a 100).
3. Solo escribe si el nombre cambió (no-op si es el mismo).
4. **Auditoría:** `MovimientoCliente` con `tipo_movimiento='edicion_nombre'` y
   `comentarios="Nombre corregido desde la bandeja WhatsApp: '<anterior>' → '<nuevo>'"`.
   La auditoría va en try/except: si fallara, NO bloquea la corrección.
5. Devuelve el nombre ya guardado para que la UI actualice al vuelo.

## Confirmado: el relleno automático no revierte la corrección

`_match_or_create_cliente` rellena el nombre automático **solo** `if nombre and not
cliente.nombre` (`whatsapp_api_views.py:73-75`). Es decir: una vez que el cliente
tiene nombre (sea auto o corregido), un mensaje entrante posterior **no lo toca**.
Tu criterio de aceptación "un mensaje entrante NO revierte el nombre corregido"
se cumple. (No cambié esa lógica.)

## Validación hecha

- `manage.py check`: 0 issues.
- La ruta resuelve a `editar_nombre` con el kwarg `phone` (incluye `+`).
- Caminos de validación probados (sin DB): sin key→401, GET→405, nombre vacío→400,
  body sin nombre→400.
- Happy path (cambio + auditoría) no se pudo correr contra DB local (esquema
  incompleto por drift AR-034); la lógica reusa el patrón ya probado de
  `_match_or_create_cliente` + `marcar_atendido`.

## Tu lado (aremko-cli)

Proxy Go `POST /whatsapp/conversations/{phone}/editar-nombre` (agrega X-API-Key,
igual que `WhatsAppMarcarAtendido`) + lápiz ✏️ inline en el encabezado de
`ConversacionWhatsApp.tsx`. Tras el `200`, usa `cliente_nombre` de la respuesta
para actualizar el encabezado y refrescar la lista. Cuando lo despliegues y Jorge
lo pruebe, marca H-004 → CERRADO.
