# BRIEF H-019 — Borrador de IA (agente Luna) para conversaciones de Instagram

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-16
**Lado que implementa:** Django (el agente vive en `whatsapp_agent`)

## Contexto
El agente IA (H-007) ya genera borradores **"✨ sugerido por IA"** para WhatsApp:
`sugerencia_agente` colgado de `GET /api/whatsapp/conversation/?phone=…&sugerencia=1`
(lazy/opt-in). Para **Instagram NO existe** — el contrato del inbox omnicanal (H-016)
dejó explícito *"sugerencia_agente solo en WA"*. Jorge quiere el **mismo borrador
también para los DMs de Instagram**.

## Pedido
Que el endpoint del hilo unificado:

```
GET /api/inbox/conversation/?canal=instagram&external_id=<igsid>&sugerencia=1
```

devuelva un campo **`sugerencia_agente`** con el **mismo shape que en WhatsApp**:
`{ texto, escalar, motivo, modo, modelo, error, generada_at, responde_a }`,
generado por el **mismo agente** (`whatsapp_agent`) usando el **historial de la
conversación de Instagram** (mensajes de `inbox_omnicanal`).

Reusar todo lo que ya existe del agente:
- Mismo grounding de catálogo vivo + disponibilidad/packs (H-009/H-011/H-015).
- Misma config singleton (`WhatsAppAgentConfig`: on/off, modo, tono, modelo, link).
- Mismo escalamiento (heurística + `[ESCALAR]`), anti-injection, fallback seguro,
  sanitización ≤1000 chars, reglas heredadas (solo se reservan online Relajación/
  Descontracturante; el resto deriva).
- **Lazy/opt-in:** solo generar con `&sugerencia=1` (NO en cada lectura ni en el
  auto-refresco), igual que WhatsApp, para no gastar LLM de más.
- **Modo borrador (human-in-the-loop):** el agente PROPONE; Jorge/Deborah edita y
  envía. NO auto-responder en IG por ahora.

## Matiz importante (IG no tiene teléfono)
La ficha del cliente del CRM se busca por teléfono; en Instagram **no hay teléfono**,
así que el borrador irá **grounded en catálogo/disponibilidad** pero **sin la memoria
del cliente por teléfono**. Es aceptable (igual es útil). Si la conversación ya está
vinculada a un `Cliente` por otro medio, úsalo; si no, generar sin ficha (no romper).

## aremko-cli (lo hace en este mismo ciclo)
- El proxy Go `/api/v1/inbox/conversation` ya reenvía `&sugerencia=1` a Django.
- `ConversacionInstagram` pide `&sugerencia=1` en la carga inicial / "Actualizar"
  (no en el auto-refresco), **precarga el borrador** en el cajón y muestra el banner
  "✨ sugerido por IA" (o "derivar a persona" si `escalar`), espejo de WhatsApp.
- Tolerante a que `sugerencia_agente` venga null/ausente (no muestra nada).

## Resultado esperado
Al abrir una conversación de Instagram en la bandeja, aparece el borrador del agente
precargado (o el aviso de derivar si escala), igual que en WhatsApp.

## Notas
- App aislada `whatsapp_agent` (drift-safe) — idealmente sin migración nueva.
- Si querés un nombre de campo o flag distinto para IG, avisá y aremko-cli se adapta;
  lo ideal es reusar `sugerencia_agente` con el mismo shape.
