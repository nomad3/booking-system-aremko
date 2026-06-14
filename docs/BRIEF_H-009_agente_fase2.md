# BRIEF H-009 — Agente IA Fase 2: conocimiento/correcciones, datos ricos y memoria

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (núcleo) + aremko-cli (UI de conocimiento)
- **Fecha:** 2026-06-13
- **Estado:** SOLICITADO
- **Contexto:** continúa H-007 (Fase 1 cerrada). Jorge detectó respuestas técnicamente correctas
  pero **incompletas/incorrectas por falta de datos o reglas**:
  - Mencionó el producto "Cacao" (no se debería ofrecer por chat).
  - "Precio tina Calbuco" → respondió "$25.000" pero ese valor es **POR PERSONA** y la tina es para
    **mín/máx 4 personas** (faltó el contexto).

> Nota conceptual (ya alineada con Jorge): NO es fine-tuning del modelo. Se mejora con **grounding +
> conocimiento + prompt**, que se puede actualizar al instante cuando cambian precios/reglas.

---

## H-009a — Base de "Conocimiento / Correcciones" (EMPEZAR POR ACÁ — máximo impacto)

Un texto editable que se **inyecta al system prompt como autoridad máxima**. Tú/Deborah agregan reglas
y correcciones; cada vez que el agente se equivoca, se agrega una línea y deja de equivocarse.

**Django:** campo `conocimiento` (TextField) en la config del agente (`AgenteWhatsAppConfig`), expuesto
por el endpoint `agente/config` que ya proxeo. Inyectarlo al prompt en un bloque claro, ej.:
`"REGLAS Y CORRECCIONES (autoridad máxima, por sobre el catálogo):\n{conocimiento}"`.
(Si prefieres un modelo lista `ConocimientoAgente` con CRUD en vez de un TextField, perfecto — avísame
el contrato y ajusto la UI; pero un TextField es el MVP más rápido.)

**aremko-cli:** textarea "Conocimiento y correcciones del agente" en la página Agente IA, guardado con
`POST /agente/config`. La armo apenas confirmes el nombre del campo.

**Ejemplos que Jorge cargaría (arreglan los casos de hoy sin tocar BD):**
- "Las tinas se cobran POR PERSONA; capacidad 1 a 4 personas. Tina Calbuco: $25.000 por persona.
  Siempre aclara que el precio es por persona y la capacidad."
- "No ofrecer el producto Cacao por este chat."
- (Heredado de H-007) "Solo los masajes de relajación y descontracturante se reservan por la web;
  el resto se coordina por WhatsApp."

## H-009b — Enriquecer los datos del catálogo (robustez de fondo)

Hoy el grounding pasa nombre + precio. Faltan los **atributos que dan contexto**:
- **Unidad del precio** (ej. "por persona") + **capacidad** (mín/máx) + qué **incluye** / notas.
- **Flag `ofrecible_agente`** (bool, default True) por producto/servicio → para excluir ítems como
  Cacao de raíz (sin depender del texto de conocimiento).

El agente formatea con eso: *"Tina Calbuco: $25.000 por persona, para grupos de 1 a 4 personas."*
(Campos nuevos o reuso de los existentes, a tu criterio; idealmente editables desde el admin de
producto/servicio que Jorge ya usa.)

## H-009c — Memoria del cliente (largo plazo, entre visitas)

Alimentar al agente con la **ficha del cliente** cuando exista (matcheado por teléfono): últimas
reservas/servicios, nº de visitas, ciudad, etc. → respuestas personalizadas ("ya nos visitaste,
reservaste Calbuco…"). Opcional: una **nota/memoria por cliente** (resumen) que el agente lea (y, si
quieres, actualice). Solo lectura para grounding; sin que el LLM escriba reservas.

## H-009d — Memoria de la conversación (corto plazo)

Ya existe `history_window` (últimos N mensajes; hoy 6). Para conversaciones largas: permitir subirlo y
**resumir lo antiguo** en un running-summary para no inflar tokens ni "anclar" el modelo al historial
(aprendizaje previo con Haiku). Ajuste de parámetro + lógica de resumen.

---

## Reparto y orden recomendado

| # | Qué | Django | aremko-cli |
|---|-----|--------|-----------|
| **a** | Conocimiento/correcciones → prompt | campo `conocimiento` + inyección | textarea en página Agente IA |
| **b** | Catálogo rico + flag `ofrecible_agente` | datos + grounding + admin | (admin Django; UI opcional) |
| **c** | Memoria del cliente | ficha en grounding (+nota opcional) | (display opcional) |
| **d** | history_window + resumen | parámetro + resumen | (ya hay campo en el form) |

**Orden sugerido:** a → b → c → d. La **(a)** sola ya corrige Cacao/Calbuco hoy.

## Aceptación (por parte)

- **(a)** Cargo una corrección (ej. "tinas son por persona, 1-4") → el agente responde con esa regla.
- **(b)** Preguntar precio de tina → responde precio **por persona + capacidad**; "Cacao" no se ofrece.
- **(c)** Cliente recurrente → el agente reconoce su historial.
- **(d)** Conversación larga → el agente mantiene contexto sin degradarse.

## Punteros (Django)

- Agente/grounding: app `whatsapp_agent` (de H-007) + el armado del catálogo (servicios publicados +
  productos con stock) + `ai_service`/patrón DPV.
- Config: `AgenteWhatsAppConfig` + endpoint `agente/config`.
- Cliente: modelo `Cliente` (reservas/visitas/ciudad) para H-009c.
