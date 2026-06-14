# BRIEF H-013 — Endpoint para disparar `procesar_aprendizaje` desde la UI

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (endpoint que corre el proceso) + aremko-cli (botón + resumen + historial)
- **Fecha:** 2026-06-14
- **Estado:** SOLICITADO

## Objetivo

Jorge quiere disparar `procesar_aprendizaje` (hoy comando de Shell) **con un botón en la página
"Agente IA"**, y ver el resultado en pantalla. Prefiere **manual** (no cron por ahora) para ir viendo
qué corrige el agente y dónde. Cuando confíe, lo pasamos a cron.

## Lo que pido a Django

Exponer el comando como **endpoint** (luna-key):
```
POST /api/whatsapp/agente/procesar-aprendizaje   (luna-key)
→ { ok:true, procesados:<int>, creadas:<int>, resumen?:[{fb_id, tipo}] }
```
- Clasifica los `AgenteFeedback` editados aún sin procesar (la misma lógica del comando) y crea
  `SugerenciaAprendizaje` pendientes.
- ⚠️ **Debe responder rápido.** El cliente Go que proxea tiene timeout; voy a subirlo a ~60s solo para
  esta llamada, así que: **procesa por lote acotado** (ej. hasta ~50 por llamada) y devuelve los conteos
  — si queda backlog, el botón se puede presionar de nuevo. (O async si prefieres; con que respondas el
  resumen en <60s, listo.)
- Idempotente: no reprocesar los `AgenteFeedback` ya procesados.

## Lo que hago yo (aremko-cli) — sin pedirte nada más

- **Botón "Procesar aprendizaje"** en la sección del agente → llama a este endpoint → muestra resumen
  *"Procesados X · Y sugerencias nuevas"* → refresca la lista de pendientes.
- **Historial:** reusando el `GET /api/whatsapp/agente/sugerencias-aprendizaje?estado=` que YA existe
  (filtro `aprobada`/`descartada`) → vista de "qué aprendió, dónde y cuándo".
- Etiquetas claras por ítem: **Problema** (borrador→enviado) · **Aprendizaje** (regla/precio) · **Dónde**
  (Conocimiento / Catálogo·ítem·campo).

## Aceptación

- Botón en la UI → corre el proceso → resumen en pantalla → las nuevas sugerencias aparecen en Pendientes.
- El historial muestra lo aprobado/descartado con su problema/cambio/dónde.

## Punteros
- Comando actual: `procesar_aprendizaje` (management command de `whatsapp_agent`).
- Modelos: `AgenteFeedback` (H-010 p1) + `SugerenciaAprendizaje` (H-010 p2).
- Endpoints existentes que reuso: `GET .../sugerencias-aprendizaje?estado=` + aprobar/descartar.
