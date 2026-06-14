# RESPUESTA H-008 — Mensaje de ausencia: lado Django listo

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-13 · **Responde a:** `BRIEF_H-008_mensaje_ausencia.md`
> **Estado:** 🟢 IMPLEMENTADO (lado Django) — falta deploy + migración + tu lado.

## TL;DR

Toggle "Mensaje de ausencia" implementado en Django sobre la config del agente
(`whatsapp_agent`). Cuando `ausencia_activa=True`, el **inbound devuelve una
directiva** `responder_ausencia: {mensaje}` para que tu Go auto-responda la frase
fija (con guard anti-spam por conversación). **Quién envía: tu Go** (Django no manda
a Meta directo; devuelve la directiva, como sugeriste). Con ausencia activa, el
agente IA **no** genera borrador (precedencia).

## Decisión "quién envía"

**Opción directiva** (la que propusiste): Django decide y devuelve el texto en la
respuesta del inbound; tu webhook Go lo envía con `SendSessionMessage` (la ventana
24h está abierta porque el cliente acaba de escribir). Django NO necesita credenciales
de la Cloud API.

## Contratos

### 1) Config — `GET/POST /api/whatsapp/agente/config` (luna-key)
Suma 3 campos (a los de H-007):
```json
{
  "ausencia_activa": false,
  "ausencia_mensaje": "¡Hola! 🌿 Gracias por escribir a Aremko Spa Boutique. En este momento no estamos atendiendo por este chat. Puedes reservar y pagar online —masajes, tinas calientes y alojamiento— en www.aremko.cl, disponible las 24 horas. Apenas retomemos la atención te respondemos por aquí. ¡Gracias por tu paciencia! 🙏",
  "ausencia_anti_spam_horas": 6
}
```
`POST` acepta `ausencia_activa` (bool), `ausencia_mensaje` (texto), `ausencia_anti_spam_horas`
(int 0–168; 0 = responder a cada mensaje).

**Tu UI:** sección "Mensaje de ausencia" en la página Agente IA → toggle
`ausencia_activa` + textarea `ausencia_mensaje` (+ opcional el campo de horas).

### 2) Directiva en el inbound — `POST /api/whatsapp/inbound`
La respuesta del inbound suma:
```json
{ "...": "...", "responder_ausencia": { "mensaje": "<frase de ausencia>" } }
```
- `responder_ausencia` es **`null`** si: la ausencia está inactiva, el entrante es una
  reacción, o el guard anti-spam suprime (ya se respondió a esa conversación dentro de
  `ausencia_anti_spam_horas`).
- **Cuando viene con `mensaje`:** tu Go lo envía con `SendSessionMessage`.

### 3) Persistir el envío SIN sacar de "pendientes" — `POST /api/whatsapp/outbound`
Cuando persistas el saliente de ausencia, **pásale el flag `no_marcar_atendido: true`**:
```json
{ "wa_message_id": "...", "to": "<phone>", "body": "<frase>", "no_marcar_atendido": true }
```
Así el saliente queda en el historial pero **la conversación sigue PENDIENTE** para
Deborah (cuando vuelve y apaga la ausencia, ve quién escribió). Sin ese flag, el
saliente limpia `requiere_atencion` como cualquier respuesta normal.

## Detalles de comportamiento (Django)

- **Anti-spam:** Django no devuelve la directiva más de una vez por conversación dentro
  de `ausencia_anti_spam_horas` (default 6). Lo registra en una tabla propia
  (`AusenciaEnviada`, una fila por teléfono). Con `0` responde a cada mensaje.
- **Precedencia sobre el agente:** con `ausencia_activa=True`, `sugerencia_agente`
  vuelve `null` (no se gasta LLM ni se sugiere borrador).
- **Solo entrantes de texto reales** (las reacciones no disparan ausencia).
- **Idempotencia:** la ausencia se evalúa solo para entrantes nuevos (después del check
  de `wa_message_id`), así que un reintento de Meta no re-dispara.
- Todo va en try/except: si algo falla, el inbound NO se rompe (solo no manda ausencia).

## Pendiente para activar

1. **Deploy** Render (push a main).
2. **Migración** en Shell de Render: `python manage.py migrate whatsapp_agent`
   (agrega 3 campos + 1 tabla; aditivo, no toca nada existente).
3. **Tu lado:** UI del toggle + Go (enviar la directiva + persistir con
   `no_marcar_atendido:true`).
4. Prender desde el form/admin y probar con el número de prueba.

## Validación (Django)

- 9/9 tests de lógica aislada (incluye la ventana anti-spam `debe_enviar`).
- `manage.py check`: 0 issues.
- Smoke test de imports + contratos (config expone los 3 campos; reacción → sin ausencia).
