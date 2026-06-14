# BRIEF H-008 — Botón "Mensaje de ausencia" (auto-respuesta fija)

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (auto-respuesta en el inbound + config) + aremko-cli (toggle + editor)
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO

## Objetivo

Un **toggle manual** "Mensaje de ausencia". Cuando está **activo**, a cada cliente que escribe se le
responde automáticamente una **frase fija** (ej. "en este horario solo atendemos por www.aremko.cl…").
Cuando se **desactiva**, vuelve el flujo normal (Deborah responde, con el borrador del agente IA).

Es independiente del agente IA (H-007), aunque puede convivir: cuando la ausencia está activa, **tiene
precedencia** y no hace falta generar borrador.

## Config (Django)

Agregar (a `AgenteWhatsAppConfig` o config dedicada, a tu criterio), editable vía el endpoint que ya
proxea aremko-cli (`GET/POST /api/whatsapp/agente/config`):
- `ausencia_activa` (bool, default False)
- `ausencia_mensaje` (text, default = la frase sugerida abajo)

## Comportamiento (Django, en el inbound)

Cuando llega un entrante (`type='text'`, no reacción) y `ausencia_activa=True`:
1. **Responder** al cliente con `ausencia_mensaje` (la ventana de 24h está abierta porque el cliente
   acaba de escribir → texto libre permitido).
2. **Anti-spam (recomendado):** enviar la ausencia **a lo más una vez por conversación cada N horas**
   (ej. 4-6h), para no repetir la misma frase a quien manda 5 mensajes seguidos. Jorge pidió "a cada
   mensaje", pero sugiero este guard; lo dejo a tu criterio (Django tiene el estado de la conversación).
3. **Precedencia:** con ausencia activa, no generes/auto-no apliques el borrador del agente IA.
4. Registrar el saliente (marcar `origen='ausencia'` si sirve para métricas/indicador).

**Quién envía:** lo dejo a tu criterio — si Django ya puede enviar por la Cloud API, hazlo ahí; si no,
devuelve una directiva en la respuesta del inbound (`responder_ausencia: {mensaje}`) y el webhook Go
de aremko-cli lo envía con `SendSessionMessage` (ya lo tiene). Avísame qué prefieres y calzo mi lado.

## Lado aremko-cli (lo hago yo)

- **UI:** sección "Mensaje de ausencia" en la página **Agente IA** — toggle `ausencia_activa` + textarea
  `ausencia_mensaje`, guardado con el `POST /agente/config` existente. Muestra estado.
- **Webhook Go:** solo si decides la opción "directiva" (yo envío); si Django envía, mi lado es solo la UI.

## Redacción sugerida (default del `ausencia_mensaje`)

> ¡Hola! 🌿 Gracias por escribir a Aremko Spa Boutique. En este momento no estamos atendiendo por este
> chat. Puedes reservar y pagar online —masajes, tinas calientes y alojamiento— en www.aremko.cl,
> disponible las 24 horas. Apenas retomemos la atención te respondemos por aquí. ¡Gracias por tu
> paciencia! 🙏

(Editable desde el formulario.)

## Aceptación

- Activo el toggle → un cliente que escribe recibe la frase de ausencia automáticamente.
- Desactivo → los mensajes vuelven al flujo normal (Deborah / borrador agente), sin auto-respuesta.

## Punteros (Django)

- Inbound: `ventas/views/whatsapp_api_views.py` (`inbound`, `_outbound_side_effects`).
- Config: la misma de H-007 (`AgenteWhatsAppConfig`) + endpoint `agente/config`.
- Envío (si va por Django): donde el agente/otros mandan por Cloud API.
