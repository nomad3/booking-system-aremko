# BRIEF H-007 — Agente IA que contesta WhatsApp (plan por fases)

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (núcleo del agente + grounding + config) + aremko-cli (UI de control + mostrar borradores)
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO
- **Relacionado:** proyecto "Agentes IA Aremko" (agente ventas multicanal)

## Objetivo

Un agente IA que responde los WhatsApp entrantes de clientes, **exclusivamente sobre lo que Aremko
ofrece**: servicios **publicados en la web** y productos con **stock > 0**. Configurable (modelo desde
Render, tono/idioma desde un formulario en aremko-cli) y con **botón on/off** desde aremko-cli.

## Principio rector (decisión de Jorge + recomendación)

**Arrancar human-in-the-loop, no en auto total.** El riesgo no es técnico sino que el agente
alucine precios/disponibilidad, prometa reservas o conteste con mal tono a un cliente real (no se
puede deshacer un envío). Por eso, **3 fases**; el botón on/off de auto-respuesta es la Fase 3.

---

## Arquitectura

- **El agente vive en Django** (pegado a los datos: servicios/productos/stock/reservas/`LeadConversation`,
  y ya existe el patrón del agente DPV + `ai_service.py`). Se dispara en el **inbound** (tras
  `PostWhatsAppInbound` / al crear el `WhatsAppMessage` entrante).
- **aremko-cli** aporta la **UI de control** (on/off, modo, editor de tono, ver modelo activo) y
  **muestra los borradores** en la bandeja.
- **Solo lectura para grounding**: el LLM NUNCA dispara escrituras (sin auto-reservas/pagos).

## Configuración

- **Desde Render (env, lo lee Django):** `WHATSAPP_AGENT_MODEL` (ej. un modelo OpenRouter),
  `WHATSAPP_AGENT_TEMPERATURE`. (La API key del LLM ya existe.)
- **Desde formulario en aremko-cli (config editable sin redeploy → modelo singleton en Django):**
  `activo` (on/off), `modo` (`borrador` | `auto_info` | `auto`), `persona_tono` (voz de marca /
  idioma), opcional `horario_activo`. Criterio de Jorge: features IA = formularios admin, no env.

## Grounding (lo que hace que conteste SOLO lo de Aremko)

NO se logra solo con el prompt: hay que **inyectar el catálogo vivo en cada llamada**.
- **Servicios** → los **publicados en la web** (reusar el mismo queryset/fuente que usa el sitio público).
- **Productos** → los de **stock > 0**.
- Precios/disponibilidad **siempre en vivo, nunca hardcodeados**. Para reservar/cotizar, el agente
  **NO confirma**: informa y deriva al link de reserva o a un humano.

---

## FASE 1 — Borrador asistido (arrancar aquí)

**Django:**
- Al entrar un mensaje (type `text`, no reacción), generar un **borrador de respuesta** (LLM +
  grounding + system prompt) y guardarlo asociado a la conversación (campo/modelo `sugerencia_agente`).
- Exponerlo: el endpoint de detalle `GET /api/whatsapp/conversation/?phone=` (o uno nuevo
  `GET /api/whatsapp/agente/sugerencia?phone=`) devuelve `{ sugerencia: {texto, generada_at, modo, escalar:bool, motivo_escalar} }` para el último entrante sin responder.
- Si las reglas de escalamiento aplican → `escalar=true` y `texto` vacío o una nota ("derivar a persona").

**aremko-cli:**
- En la bandeja/Mensajes, si hay sugerencia, **pre-cargar el cajón de respuesta** con el texto
  (editable) + etiqueta "✨ sugerido por IA"; Deborah edita y envía (reusa el flujo de reply
  existente) o lo descarta. Si `escalar=true`, mostrar el aviso en vez del borrador.

**Aceptación F1:** ante un entrante, aparece un borrador correcto y dentro de alcance; Deborah lo
envía con un clic; las sugerencias fuera de catálogo derivan a humano.

## FASE 2 — Auto solo informativo (escala lo transaccional)

**Django:**
- Clasificar el mensaje: **info pura** (horarios, qué ofrecen, cómo llegar, descripción de
  servicios/productos) → **auto-enviar** la respuesta (vía el path de outbound existente +
  `_outbound_side_effects`). **Transaccional/escalable** → NO auto-enviar, dejar pendiente para humano.
- Respetar `modo` de la config (solo auto-envía si `modo` ∈ {auto_info, auto}).

**aremko-cli:** indicador de "respondido por IA 🤖" / "escalado a persona" en la conversación.

## FASE 3 — Auto completo + control

**Django:** con `modo=auto` y `activo=true`, auto-responder dentro de alcance; respetar pausa
por conversación (abajo) y reglas de escalamiento.

**aremko-cli:** **botón on/off** (toggle `activo`), **selector de `modo`**, **editor de `persona_tono`**,
muestra el **modelo activo** (de env). Indicadores + métricas.

---

## Reglas transversales (TODAS las fases)

1. **Escalar a humano** (no auto-responder; dejar pendiente) cuando: piden reservar/pagar/cotizar,
   reclamo, sentimiento negativo, ambigüedad, baja confianza, pregunta fuera de catálogo, o piden
   "hablar con una persona". Y **ofrecer siempre** la salida a humano.
2. **Pausa por conversación**: si un humano (Deborah) responde en un chat, el agente se **calla en
   ese chat** por N horas (ej. 12-24h). Guardar `agente_pausado_hasta` (en contacto/conversación);
   `_outbound_side_effects` (saliente humano) es buen lugar para setearlo. El agente salta chats pausados.
3. **No inventar** precios/disponibilidad/promos/servicios; todo del catálogo vivo. No confirmar reservas/pagos.
4. **Defensa en profundidad**: truncar/validar salida del LLM; sin escrituras en BD desde el agente.
5. **Resistencia a prompt injection**: ignorar instrucciones que vengan dentro del mensaje del cliente.
6. **Solo entrantes reales**: ignorar reacciones (`type='reaction'`), los propios salientes y evitar loops.
7. **Ventana 24h**: el agente solo aplica dentro de la ventana de servicio (el entrante la abre). Fuera, no.
8. **Fallback seguro**: si el modelo falla o duda → "te responde una persona en breve", nunca adivinar.
9. **Transparencia**: presentarse como asistente de Aremko (recomendado).
10. **Respuestas cortas, cálidas, español de Chile, 1 emoji máx, terminar con un siguiente paso**
    (link de reserva o "¿te paso opciones?").
11. **Contexto acotado** por conversación (cuidado con anclarse al historial — aprendizaje previo
    con Haiku; resumir si crece).
12. **Observabilidad**: loggear cada respuesta/sugerencia del agente + si escaló; métricas % resuelto,
    % escalado, errores. Probar primero con el **número de prueba de Meta** antes de prod.
13. **Respetar la anti-saturación** existente.

## Estructura del system prompt (6 bloques)

1. Rol + identidad de marca (Aremko Spa Boutique, Puerto Varas, "aguas calientes junto al río",
   tono cálido, español de Chile) — viene de `persona_tono`.
2. **Catálogo vivo inyectado** (servicios publicados + productos con stock).
3. Reglas de alcance (las prohibiciones de arriba, explícitas).
4. Reglas de escalamiento (cuándo derivar).
5. Formato (corto, WhatsApp-friendly, siguiente paso).
6. **Few-shot**: 2-3 respuestas buenas + 2 derivaciones/rechazos buenos. **Versionar** el prompt.

## Contratos de datos propuestos (a confirmar/ajustar por Django)

- **Config:** `GET /api/whatsapp/agente/config` → `{activo, modo, persona_tono, modelo (read-only,
  de env), pausado_global?}`; `POST /api/whatsapp/agente/config` `{activo, modo, persona_tono}` (luna-key).
- **Sugerencia (F1):** en `GET /api/whatsapp/conversation/?phone=` agregar
  `sugerencia_agente: {texto, generada_at, modo, escalar, motivo} | null`.
- **Estado por mensaje:** marcar los salientes del agente (`origen='agente_ia'`) para indicadores/métricas.
- Si cambias nombres/forma, avísame y ajusto el lado aremko-cli.

## Reparto

| Lado | Qué |
|------|-----|
| **Django** | núcleo del agente (LLM + grounding servicios publicados/stock), config singleton, generación de borrador, clasificación info/transaccional, auto-envío gateado, pausa por conversación, escalamiento, logging |
| **aremko-cli** | formulario de control (on/off, modo, tono, modelo activo), mostrar borrador en la bandeja, indicadores "🤖/escalado", vista de métricas |

## Punteros (Django, a reusar)

- LLM: `ventas/services/ai_service.py`; patrón agente: el agente DPV (`LeadConversation`, grounding
  de catálogo, `check_dpv_agent`).
- Inbound: `whatsapp_api_views.py` (`inbound` / `_match_or_create_cliente`); outbound + `_outbound_side_effects`.
- Catálogo: queryset de servicios publicados (fuente del sitio público) + productos con stock.
- Conversaciones: `conversations` / `conversation` (de aquí cuelga la sugerencia).

## Aceptación global

Fase a fase (arriba). Cierre del H-007 cuando la Fase 1 esté validada por Jorge en prod; las Fases
2-3 pueden ser sub-iteraciones (H-007b/c) o validaciones incrementales según prefieras.
