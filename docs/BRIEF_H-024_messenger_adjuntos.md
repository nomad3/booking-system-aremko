# BRIEF H-024 — Adjuntos entrantes de Facebook Messenger (foto/video/audio/documento)

**Pedido de Jorge (2026-06-18):** recibir archivos, fotos, documentos y audios por
Messenger en la bandeja, igual que ya se hace con Instagram (H-020) y WhatsApp.

**Mirror exacto de H-020 (Instagram adjuntos).** El modelo `ChannelMessage` ya tiene
`media_file` (Cloudinary RAW) / `mime_type` / `original_filename` y el endpoint
`POST /api/instagram/inbound-media`. Esto pide **el equivalente para Messenger**.

## Lo que pide (lado Django)

Nuevo endpoint **`POST /api/messenger/inbound-media`** — espejo de
`/api/instagram/inbound-media` pero con `canal='messenger'`.

- **Auth:** header `X-API-Key: LUNA_API_KEY`.
- **Body multipart/form-data** (lo que ya manda aremko-cli):
  - `fb_message_id` (str) — idempotencia
  - `from_psid` (str)
  - `to_page_id` (str)
  - `is_echo` (`true`/`false`)
  - `type` (str): `image | video | audio | file`
  - `timestamp` (str, epoch segundos)
  - `contact_name` (str, puede venir vacío → fallback `Cliente Messenger #PSID`)
  - `caption` (str, puede venir vacío) → va como `body` del mensaje
  - `mime_type` (str)
  - `file` (el archivo, ≤16 MB; aremko-cli ya corta a 16 MB)
- **Comportamiento (igual que instagram inbound-media):**
  - Idempotente por `fb_message_id`.
  - Conversación keyeada por el **PSID del cliente** = el que NO es la Página
    `555157687911449` (eco→`to_page_id`, entrante→`from_psid`) — **misma resolución
    que ya tienen funcionando para el inbound de texto de Messenger** (H-023).
  - `is_echo:true` → saliente (no marca pendiente; clear-on-echo).
  - Guarda `media_file` en Cloudinary (RAW), `mime_type`, `original_filename`.
  - `type` → `ChannelMessage.type`; `body` = caption.
  - Responde `200` (mismo shape que instagram inbound-media).

## Front + Go (aremko-cli) — YA HECHO y desplegado

- Go: `messenger.DownloadMedia` (baja bytes del CDN de Meta, sin token) +
  `bookings.PostMessengerInboundMedia` (multipart) + `handleMessengerMedia`
  (por cada adjunto descarga y sube; el texto va como caption del 1er adjunto;
  adjuntos extra → sufijo `#i` en el id para no chocar idempotencia).
- Front: **sin cambios** — `ConversacionInstagram` (que Messenger reusa) ya
  renderiza foto/video/audio/documento de forma genérica por `type`/`mime`.

⇒ Apenas exista `/api/messenger/inbound-media`, los adjuntos de Messenger
aparecen solos en la bandeja. Hoy aremko-cli ya los intenta subir y loguea
`error subiendo adjunto a Django` (404) hasta que el endpoint exista.

**Mirror de:** H-020 (Instagram) + H-023 (Messenger texto).
