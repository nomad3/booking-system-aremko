# BRIEF H-004 — Editar el nombre del cliente desde la bandeja de WhatsApp

- **Solicita:** agente aremko-cli
- **Implementa:** Django (endpoint) + aremko-cli (UI). Este brief cubre el lado **Django**.
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO

## Contexto / necesidad (de Jorge)

En "Mensajes WhatsApp" y la Bandeja, el nombre que se muestra = `Cliente.nombre`.
Para los que escriben por primera vez, Django auto-crea la ficha con el **nombre de
perfil de WhatsApp** o `"WhatsApp <teléfono>"` (`_match_or_create_cliente`,
`whatsapp_api_views.py:63`). Ese nombre **muchas veces no coincide con el real** y Deborah
necesita **corregirlo** desde la conversación, sin entrar al admin.

Editar `Cliente.nombre` corrige la **ficha canónica** → se refleja en CRM, reservas,
reportes y próximos mensajes. Es lo deseado (es una corrección, no un alias solo-chat).

## Contrato propuesto del endpoint (sigue el patrón de `marcar-atendido`)

```
POST /api/whatsapp/conversations/<str:phone>/editar-nombre/
Auth: luna-key (X-API-Key)  — mismo guard que el resto de /api/whatsapp/*
Body JSON: { "nombre": "Nombre Real" }
```

**Comportamiento:**
1. `_match_or_create_cliente(phone)` para obtener la ficha por teléfono (ya existe en el
   archivo; reúsalo).
2. Setear `cliente.nombre = nombre.strip()[:100]` (el resto del código ya trunca a 100).
3. **Validar:** rechazar vacío/solo-espacios → 400 `{"ok": false, "error": "nombre requerido"}`.
4. **Auditar:** registrar el cambio en `MovimientoCliente` (CLAUDE.md lo señala como la traza
   de cambios de ficha) — nombre anterior → nuevo, origen "bandeja WhatsApp".
5. **Responder:** `{"ok": true, "cliente_id": <id>, "cliente_nombre": "<nuevo>"}` para que
   la UI actualice al vuelo.

**Nota importante (ya está bien en el código, solo confirmar):** `_match_or_create_cliente`
solo rellena el nombre automático `if nombre and not cliente.nombre` → un mensaje entrante
**no debe pisar** la corrección manual. Confirmar que sigue así tras el cambio.

## Lado aremko-cli (lo hace el agente aremko-cli, NO Django)

- **Backend Go:** proxy `POST /whatsapp/conversations/{phone}/editar-nombre` → cliente
  bookings agrega la X-API-Key (igual que `WhatsAppMarcarAtendido`).
- **Frontend:** lápiz ✏️ junto al nombre en el encabezado de `ConversacionWhatsApp.tsx`
  (recién agregamos ahí nombre + teléfono, H sin número / commit `a942fa2`); edición inline
  → llama al proxy → actualiza nombre mostrado + refresca la lista.

## Aceptación

- `POST .../editar-nombre/` con un nombre válido cambia `Cliente.nombre` en BD, queda
  auditado, y la conversación en aremko-cli muestra el nombre nuevo sin recargar.
- Un mensaje entrante posterior NO revierte el nombre corregido.

## Punteros (Django)

- Vista/endpoints WhatsApp: `ventas/views/whatsapp_api_views.py` (`_match_or_create_cliente` L63, `conversations` L468, `marcar_atendido` como patrón de acción por `<phone>`).
- URLs: `aremko_project/urls.py:71-73`.
- Auditoría: `MovimientoCliente` (ver `/auditoria-movimientos/`).
