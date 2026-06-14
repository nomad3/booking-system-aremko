# RESPUESTA H-007 (Fase 1) — Agente IA WhatsApp: núcleo Django listo

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-007_agente_whatsapp_ia.md`
> **Estado:** 🟢 IMPLEMENTADO (lado Django, Fase 1) — falta deploy + tu lado.

## TL;DR

Fase 1 (borrador asistido) implementada en Django como **app nueva aislada**
`whatsapp_agent` (drift-safe: migración `0001_initial` sin dependencias, no toca
AR-034). El agente **lee** catálogo vivo + genera un borrador y lo deja colgado de
la conversación; **no envía nada** (eso lo hace Deborah desde tu UI). Arranca
**apagado** (`activo=False`) hasta que Jorge lo prenda desde el admin.

## ⚠️ 2 cambios de contrato vs. el brief (decisión técnica, dime si te sirve)

1. **El modelo va en el formulario, no en env.** El brief proponía
   `WHATSAPP_AGENT_MODEL` en Render. Pero `ai_service.py` es **DeepSeek** (variaciones
   de email), no sirve. El patrón correcto es el **agente DPV** (OpenRouter), que pone
   el modelo en su config editable. Así que `model_name`/`temperature` quedaron en el
   form del agente (con fallback a `DPV_LLM_MODEL` de env si lo dejas vacío). Encaja
   mejor con el criterio de Jorge ("IA = formularios, no env") y te da más control.
2. **La sugerencia se genera *lazy* al pedir la conversación, no en el inbound, y
   es OPT-IN.** Generarla en el webhook inbound metía latencia de LLM en el hot-path
   de Meta (1 worker Gunicorn). En su lugar, `GET /api/whatsapp/conversation/?phone=`
   la genera (o recupera de cache) **solo si pasas `?sugerencia=1`** (default = NO
   genera). Así prender el agente no dispara gasto de LLM en cada apertura de chat de
   tu bandeja actual hasta que conectes el parámetro a propósito. Cacheada por
   `wa_message_id` (no regenera al reabrir). **Acción tu lado: agregar `&sugerencia=1`
   a la llamada de detalle de conversación cuando quieras el borrador.**

Si prefieres otra forma (p.ej. un endpoint dedicado `GET /api/whatsapp/agente/sugerencia`),
avísame y lo agrego — el núcleo ya está, es solo exponerlo distinto.

## Contratos de datos (lo que tu lado consume)

### 1) Config del agente — `GET/POST /api/whatsapp/agente/config`
Auth: header `X-API-Key` (luna-key, igual que el resto de `/whatsapp/`).

`GET` →
```json
{
  "ok": true,
  "config": {
    "activo": false,
    "modo": "borrador",                 // borrador | auto_info | auto
    "persona_tono": "Eres el asistente virtual de Aremko...",
    "link_reserva": "https://www.aremko.cl/",
    "model_name": "",                    // vacío = usa modelo_efectivo
    "modelo_efectivo": "anthropic/claude-haiku-4.5",
    "temperature": 0.4,
    "max_tokens": 350,
    "history_window": 6,
    "pausa_horas_tras_humano": 12,
    "prompt_version": "f1-2026-06-13"
  }
}
```

`POST` (body = subconjunto de campos a cambiar) →
```json
{ "activo": true, "modo": "borrador", "persona_tono": "...", "link_reserva": "...",
  "model_name": "anthropic/claude-haiku-4.5", "temperature": 0.4,
  "max_tokens": 350, "history_window": 6, "pausa_horas_tras_humano": 12 }
```
Valida `modo` (enum) y rangos numéricos (`temperature` 0–2, `max_tokens` 1–4000,
`history_window` 0–50, `pausa_horas_tras_humano` 0–168). Devuelve
`{ok, actualizado:[campos], config:{...}}`.

**Para tu formulario de control** (Fase 3 del reparto, pero el endpoint ya está):
toggle `activo`, selector `modo`, textarea `persona_tono`, campo `link_reserva`,
`model_name` (avanzado) y muestra `modelo_efectivo` como read-only.

### 2) Borrador en el detalle — `GET /api/whatsapp/conversation/?phone=<E164>&sugerencia=1`
**Opt-in:** sin `sugerencia=1`, `sugerencia_agente` vuelve `null` (no genera ni gasta LLM).
La respuesta existente suma una clave:
```json
{
  "phone": "...", "cliente_id": 1, "count": 12, "messages": [...],
  "sugerencia_agente": {
    "texto": "¡Hola! 😊 Sí, tenemos masajes de relajación. ¿Lo quieres para una o dos personas?",
    "escalar": false,
    "motivo": "",
    "modo": "borrador",
    "modelo": "anthropic/claude-haiku-4.5",
    "error": "",
    "generada_at": "2026-06-13T23:50:00+00:00",
    "responde_a": "wamid.XXX"        // el entrante que responde
  }
}
```
- `sugerencia_agente` es **`null`** si: el agente está OFF, no hay entrante sin
  responder, el chat está pausado (humano respondió hace < N h), o pasaste `?sugerencia=0`.
- Si **`escalar: true`** → `texto` viene vacío y `motivo` explica por qué derivar
  (reclamo, fuera de catálogo, pidió humano, etc.). **No precargues el cajón**; muestra
  el aviso "⚠️ Derivar a una persona — {motivo}".
- Si **`error`** no está vacío (modelo no disponible) → también viene `escalar:true`;
  es el fallback seguro (que conteste un humano), no un bug.

**Tu lado (Fase 1):** si `sugerencia_agente` y `!escalar` → precarga el cajón de
respuesta con `texto`, editable, con la etiqueta "✨ sugerido por IA". Deborah edita y
manda con tu flujo de reply existente (no cambia el outbound).

## Lo que hace el núcleo (para que sepas qué esperar)

- **Grounding**: inyecta en cada llamada los servicios `publicado_web=True, activo=True`
  y productos `publicado_web=True, cantidad_disponible>0`, con precio en vivo. Nunca
  inventa; si no está en el catálogo, deriva.
- **System prompt en 6 bloques** (rol+marca / catálogo / alcance / escalamiento /
  formato / few-shot), versionado (`prompt_version`).
- **Escalamiento**: heurística por palabras clave **antes** de gastar tokens (pide
  humano, reclamo, sentimiento negativo) + el modelo puede marcar `[ESCALAR: motivo]`.
- **Pausa por conversación** (solo modos AUTO): si hay un saliente humano en las
  últimas `pausa_horas` (default 12), el agente se calla en ese chat. **En modo
  `borrador` NO aplica** — sugerir es inofensivo (no envía), así que siempre se ofrece
  un borrador aunque haya un saliente reciente.
- **Resistencia a prompt injection**: el mensaje del cliente va envuelto como DATOS;
  el system prompt ordena ignorar instrucciones embebidas.
- **Defensa en profundidad**: salida truncada a ≤1000 chars (muy por debajo de los
  4096 de WhatsApp), sin escrituras al negocio (el agente solo escribe su propia tabla
  de sugerencias).
- **Observabilidad**: cada sugerencia se guarda (`SugerenciaAgenteWhatsApp`) con tokens,
  latencia, modelo, si escaló. Visible en el admin Django (solo lectura).

## Pendiente para activar (orden)

1. **Deploy** a Render (push a main).
2. **Migración** en el Shell de Render: `python manage.py migrate whatsapp_agent`
   (auto-migraciones están off). Crea 2 tablas nuevas; no toca nada existente.
   *Hasta que corra, `sugerencia_agente` simplemente vuelve `null` (está en try/except,
   no rompe la conversación).*
3. **Probar el borrador SIN prender nada** (comando de prueba, desde el Shell de
   Render): `python manage.py probar_agente_wa --mensaje "Hola, hacen masajes?"`
   o `--phone <número de prueba>`. Genera el borrador con catálogo + LLM reales y lo
   imprime; no envía nada ni requiere `activo=True`. Es el "probar con el número de
   prueba de Meta" del brief, sin exponerlo a clientes.
4. **Prender el agente** desde el admin Django (`Configuración Agente WhatsApp` →
   `activo=True`, modo `borrador`) — o vía `POST .../agente/config`. (Con opt-in, esto
   es inofensivo hasta que tu lado pida `?sugerencia=1`.)
5. **Tu lado**: llamar a la conversación con `&sugerencia=1` y precargar el cajón con
   `sugerencia_agente.texto` + etiqueta IA.

## Validación hecha (Django)

- 8/8 tests de lógica aislada (grounding, precios, escalamiento, anti-injection,
  prompt) — sin DB ni LLM.
- `manage.py check`: 0 issues.
- Smoke test de imports en runtime (vistas + agente + provider OpenRouter) OK.
- Medición real (calidad de borradores, % escala) → en prod con el número de prueba,
  fase a fase. Los borradores que Deborah corrija son el material para afinar el prompt.

Cuando tengas tu lado y Jorge valide F1 en prod con el número de prueba → H-007 a
INTEGRADO/CERRADO. F2 (auto-info) y F3 (auto+botón) quedan como iteraciones.
