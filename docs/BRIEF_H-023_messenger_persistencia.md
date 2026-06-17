# BRIEF H-023 — Persistencia de Facebook Messenger en la bandeja (omnicanal)

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-16
**Lado que implementa:** Django (persistencia/reads, app `inbox_omnicanal`)
**Es un mirror casi exacto de H-016 (Instagram), porque el modelo ya es channel-agnostic.**

## Contexto
Sumamos **Facebook Messenger** a la bandeja, igual que Instagram. Fase 0 (Meta) y Fase 1
(webhook Go) ya hechas por aremko-cli: el endpoint `GET/POST /api/v1/messenger/webhook`
recibe los DMs (mismo formato Messenger Platform que IG, `entry[].messaging[]`, object
`page`). Identidad = **PSID** (Page-Scoped ID). La Página de Aremko es `555157687911449`.
Canal **REACTIVO** (ventana 24h, sin plantillas — el marketing pagado se difirió).

## Pedido
1. **Inbound** — `POST /api/messenger/inbound` (header `X-API-Key: LUNA_API_KEY`), espejo de
   `/api/instagram/inbound` pero `canal='messenger'`:
   ```json
   {
     "fb_message_id": "<mid>",       // idempotencia
     "from_psid": "<sender.id>",     // PSID del cliente = external_id de la conversación
     "to_page_id": "555157687911449",// la Página de Aremko (recipient.id)
     "text": "...",
     "timestamp": "1718560000",
     "contact_name": "",             // aremko-cli lo resolverá vía Graph API (fase posterior)
     "is_echo": false
   }
   ```
   - Idempotente por `fb_message_id`.
   - Conversación keyeada por el **PSID del cliente** = el id que NO es la Página `555157687911449`
     (en eco = `to_page_id`/recipient; en entrante = `from_psid`/sender). Mismo criterio que IG.
   - `is_echo:true` → saliente + clear-on-echo (igual que hiciste en IG H-017).
   - Responde el mismo shape que IG: `{ok, message_id, canal:"messenger", external_id, direction, requiere_atencion, pendientes_limpiados, duplicate?}`.

2. **Reads** — el modelo `inbox_omnicanal` ya es channel-agnostic, así que idealmente
   `/api/inbox/conversations/` y `/api/inbox/conversation/?canal=messenger&external_id=<psid>`
   ya soportan el nuevo canal con solo aceptar `canal='messenger'` (igual que `instagram`/`whatsapp`).
   Confirmar que: (a) la lista unificada incluye las conversaciones de Messenger con `canal:"messenger"`;
   (b) el hilo funciona con `?canal=messenger&external_id=<psid>`; (c) `marcar-atendido` con `<canal>=messenger`.

## Fuera de alcance (fases siguientes, como en IG)
- Responder DMs de Messenger (Go vía `graph.facebook.com/{page-id}/messages`, persiste por el eco).
- Adjuntos (inbound-media), @nombre del cliente (Graph API), borrador IA, métricas.

## aremko-cli (en este ciclo, una vez exista el inbound)
- Conectar `handleMessengerEvent` (hoy solo loguea) → `POST /api/messenger/inbound`.
- Front: agregar `messenger` como canal (ícono propio) en la bandeja unificada — ya channel-agnostic.

## Notas
- Sin migración nueva si el modelo ya admite cualquier `canal` (string). Si `canal` está acotado a
  un choices, agregar `'messenger'` (drift-safe).
- Mismo `ChannelMessage`/lógica de IG; idealmente reusar el handler de inbound parametrizado por canal.
