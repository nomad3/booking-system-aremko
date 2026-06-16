# BRIEF H-016 — Persistencia de Instagram DM en la bandeja (omnicanal, Fase 2)

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-16
**Lado que implementa:** Django (la persistencia y los reads de la bandeja viven aquí)
**Proyecto:** Bandeja omnicanal — sumar Instagram DM al inbox de WhatsApp ya existente.

---

## Contexto

Tras dejar WhatsApp en producción, el siguiente canal es **Instagram DM**. La meta:
que Deborah/Jorge respondan **WhatsApp + Instagram desde la misma bandeja** de
aremko-cli, con el contexto del CRM al lado. Va por fases:

- **Fase 0 (Meta)** ✅ — cuenta `aremkospa` conectada a la app `aremko-wa2` por la ruta
  **Instagram Login**; permisos `instagram_business_manage_messages`; webhook verificado
  y campo `messages` suscrito. IG Business Account ID = **`17841400756478364`**.
- **Fase 1 (aremko-cli, Go)** ✅ — endpoint `GET/POST /api/v1/instagram/webhook` recibe
  los DMs entrantes desde Meta, valida firma HMAC y hoy **solo los loguea**. Probado
  end-to-end (POST 200 + parseo correcto). El backend Go ya tiene el token y el
  IG Business ID.
- **Fase 2 (ESTE BRIEF — Django)** — **guardar** los DMs de Instagram y exponerlos en la
  bandeja, igual que un WhatsApp. Es el cimiento de todo lo visible.

> ⚠️ Instagram es un canal **REACTIVO**: solo se responde dentro de la ventana de 24h;
> **no hay plantillas ni campañas masivas** (eso es exclusivo de WhatsApp). Así que NO
> se replica nada del flujo de Bandeja/plantillas/aprobación (H-012/H-014) para IG.

---

## El problema central: la identidad NO es el teléfono

Hoy toda la persistencia de WhatsApp se keyea por `phone` (E.164) y se vincula al
`Cliente` por `Cliente.telefono` (unique). **Instagram no tiene teléfono.** La identidad
de un DM es el **IGSID** (Instagram-Scoped ID del usuario que escribe, ej. `12334567890`),
un identificador opaco por-usuario-por-app.

Implicancias que el modelo debe soportar:
1. Una conversación de Instagram se identifica por **`(canal=instagram, external_id=IGSID)`**,
   no por teléfono.
2. Un contacto de Instagram **puede NO tener `Cliente`** asociado (no hay teléfono para
   matchear). El modelo debe permitir una conversación "huérfana" identificada solo por
   IGSID, con vínculo a `Cliente` **opcional** (y enriquecible después: si el cliente
   comparte su teléfono en el chat, o vinculación manual desde la ficha).
3. El webhook de IG **no trae el nombre/usuario** del que escribe (solo el IGSID).
   aremko-cli puede resolver `IGSID → @username/nombre` con una llamada a la Graph API
   (tiene el token) y mandarlo como `contact_name`; mientras tanto, el fallback es el
   propio IGSID o el `@username` cuando esté.

**Precedente útil en este mismo repo:** `destino_puerto_varas` ya tiene un modelo
multi-canal — `LeadConversation(channel, external_id)` con `get_or_create_conversation(channel, external_id)`
y `ChannelType.choices` en `enums.py`. Sirve como patrón de referencia (no necesariamente
para reusar tal cual, pero la forma `(channel, external_id)` es la correcta).

---

## Lo que aremko-cli ENVIARÁ (contrato inbound — propuesta, ajustable)

El backend Go, al recibir un DM, hará un POST a Django (igual que hace hoy con
`/api/whatsapp/inbound`). Campos disponibles desde el webhook de IG:

```
POST /api/instagram/inbound          (header X-API-Key: LUNA_API_KEY)
{
  "ig_message_id": "<mid>",            // idempotencia (unique por canal)
  "from_igsid":    "<sender.id>",      // IGSID del cliente = external_id de la conversación
  "to_igsid":      "17841400756478364",// cuenta de Aremko (recipient.id)
  "text":          "hola, ¿tienen tinas el sábado?",
  "timestamp":     "1718500000",       // epoch (Go lo normaliza a seg si hace falta)
  "contact_name":  "@juanperez",       // si aremko-cli resolvió el username; puede venir vacío
  "is_echo":       false               // true = mensaje que envió la propia cuenta (eco)
}
```

- **Idempotencia** por `ig_message_id` (como `wa_message_id`).
- **Texto primero.** Los adjuntos (foto/historia/share) llegan con una URL temporal de
  IG; el flujo de media (descargar bytes + subir a Cloudinary, como `/inbound-media` de
  WhatsApp) lo dejamos para una fase posterior (Fase 5). Para H-016 basta con texto +
  registrar el tipo si viene adjunto (cuerpo tipo "📷 Foto").
- Si el endpoint que prefieres es genérico (`/api/messages/inbound` con `{canal, ...}`)
  en vez de uno por-canal, **perfecto** — dímelo y aremko-cli se adapta. Lo importante es
  el contrato de campos, no el nombre de la ruta.

---

## Lo que la BANDEJA necesita de vuelta (reads con `canal`)

El front (Fase 3, lo hace aremko-cli) quiere mostrar **una sola lista** con WhatsApp e
Instagram mezclados por fecha, con un indicador de canal. Para eso necesita:

1. **Lista de conversaciones** con un campo nuevo **`canal`** (`"whatsapp"` | `"instagram"`)
   por conversación, e idealmente **incluyendo las de Instagram** en la misma respuesta.
   - Hoy `GET /api/whatsapp/conversations/` devuelve `conversations[]` con
     `phone, cliente_id, cliente_nombre, ultimo_mensaje, ultimo_direction, ultimo_timestamp,
     sin_responder, requiere_atencion, total_mensajes`.
   - Para IG, `phone` no aplica → se necesita una **clave de conversación** genérica. Propuesta:
     agregar `canal` + `external_id` (para WA, `external_id` = el teléfono; para IG, el IGSID),
     manteniendo `phone` por compatibilidad cuando el canal es WhatsApp.
   - El **orden** (pendientes primero, luego recencia — H-006) debe valer cruzando ambos canales.
2. **Hilo de una conversación**: hoy el front pasa `?phone=`. Para IG necesitará identificar
   la conversación por `(canal, external_id)` — ej. `?canal=instagram&external_id=<igsid>`
   (o el esquema que definas). Cada mensaje del hilo debería traer su `canal`.
3. **Marcar atendido** equivalente para IG (el botón "✓ Leído" / `requiere_atencion`, H-005),
   por `(canal, external_id)`.

> Decides tú si esto se logra **extendiendo** los endpoints `/api/whatsapp/*` para que sean
> channel-aware, o con **endpoints nuevos** (`/api/inbox/conversations/` unificado). aremko-cli
> ajusta el proxy/UI a lo que definas; solo necesitamos que la respuesta diga el `canal` y que
> la conversación se pueda identificar por `(canal, external_id)`.

---

## Alcance de H-016 (acotado, para que sea entregable)

**Incluye:**
- Modelo de persistencia para mensajes de Instagram (texto), con identidad `(canal, external_id=IGSID)`,
  vínculo a `Cliente` **opcional**, idempotente por `ig_message_id`.
- Endpoint inbound para que aremko-cli guarde los DMs.
- Reads de bandeja **channel-aware** (lista + hilo + marcar-atendido) para que el front
  muestre WhatsApp + Instagram juntos, con `canal` por conversación/mensaje.

**NO incluye (fases siguientes, otros handoffs):**
- **Outbound / responder** DMs de IG (Fase 4 — necesita el token de envío y el endpoint de
  registro de saliente). Será H-017.
- **Adjuntos** entrantes/salientes de IG (Fase 5).
- **Agente IA** sobre IG (después; IG es reactivo, el agente sugiere igual que H-007 pero
  eso es fase aparte).
- Cualquier campaña/plantilla (no aplica a IG).

---

## Enfoques sugeridos (NO mandato — tú conoces el drift)

El Explore del lado aremko-cli observó que `ventas.WhatsAppMessage` y `ContactoWhatsApp`
están en `ventas` (congelado por AR-034). Por eso, **opciones** a tu criterio:

- **(Recomendado, drift-safe)** App nueva aislada (ej. `messaging` / `inbox_omnicanal`) con
  un modelo `ChannelMessage(canal, external_id, external_message_id, cliente→ventas.Cliente null,
  direction, body, msg_type, status, timestamp, requiere_atencion, …)`, migración `0001_initial`
  sin FK que arrastre `ventas` (patrón `whatsapp_agent`/`destino_puerto_varas`). La lista de
  conversaciones unifica `ventas.WhatsAppMessage` (WA legacy) + `ChannelMessage` (IG, y a futuro
  WA migra cuando convenga). Riesgo de drift mínimo.
- **(Alternativa)** Modelo `InstagramMessage` aislado, espejo de `WhatsAppMessage`, y el read
  une ambos. Más simple, menos abstracto; converge a un modelo común después.
- **(Evitar salvo que estés segura)** Tocar `ventas.WhatsAppMessage` para agregarle `canal`/`external_id`
  → migración manual sobre app congelada (AR-034). Más riesgo.

Para el match de `Cliente` desde IGSID: no hay teléfono, así que probablemente convenga una
tabla puente `ClienteExternalId(cliente, canal, external_id)` o un `JSONField` de handles —
de nuevo, a tu criterio. Para H-016 es válido empezar guardando la conversación con
`cliente=null` y `contact_name=@username`, y resolver el vínculo a `Cliente` después.

**Migraciones:** seguir el patrón drift-safe (app aislada `0001_initial`, o migración manual
si tocas `ventas`). NO `makemigrations ventas` automático.

---

## aremko-cli (qué hace de su lado una vez exista esto)

- Conecta el handler `handleInstagramEvent` (hoy solo loguea) para que haga el POST inbound
  a Django con el contrato de arriba.
- Resuelve `IGSID → @username/nombre` vía Graph API (tiene el token) y lo manda en `contact_name`.
- Frontend (Fase 3): agrega `canal` a los tipos, ícono de Instagram en la lista, cabecera
  dinámica, y consume el read unificado.
- Variables ya previstas en el backend Go: `INSTAGRAM_ACCESS_TOKEN`, `INSTAGRAM_BUSINESS_ID`
  (`17841400756478364`), `INSTAGRAM_APP_SECRET`, `INSTAGRAM_VERIFY_TOKEN`.

Queda a la espera de tu definición del contrato final (nombres de ruta + cómo identificar la
conversación en los reads) para enganchar el Go y el front.

---

## Resumen para arrancar

1. Persistir DMs de IG con identidad `(canal, external_id=IGSID)`, `Cliente` opcional,
   idempotente por `ig_message_id`. App aislada drift-safe recomendada.
2. Endpoint inbound (nombre a tu elección; contrato de campos arriba).
3. Reads de bandeja con `canal` por conversación/mensaje, identificando la conversación por
   `(canal, external_id)`, manteniendo el orden "pendientes primero".
4. Confirmar a aremko-cli el contrato final → enganchamos Go + front (Fase 3) y luego
   outbound (H-017).
