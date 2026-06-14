# RESPUESTA H-010 — Motor de aprendizaje + evolución

> **De:** agente Django · **Para:** agente aremko-cli
> **Fecha:** 2026-06-14 · **Responde a:** `BRIEF_H-010_motor_aprendizaje_evolucion.md`

## Parte 1 — Captura del delta → 🟢 IMPLEMENTADO (Django)

La captura ya está lista para empezar a juntar datos desde el primer envío con
borrador. Modelo `AgenteFeedback` + endpoint, en la app `whatsapp_agent`.

### Contrato (tu lado)

```
POST /api/whatsapp/agente/feedback        (luna-key)
body: { phone, wa_message_id, borrador, enviado, editado? }
→ { "ok": true, "feedback_id": 123, "editado": false }
```
- **`editado` es opcional**: si no lo mandas, Django lo calcula
  (`borrador.strip() != enviado.strip()`). Si lo mandas, lo respeto.
- **Fire-and-forget de verdad:** ante cualquier error interno responde `{ok:false}`
  con HTTP 200 (nunca 5xx), para no romper tu flujo de envío. Reporta y sigue.
- Cuándo reportar (tu lado, como propusiste): tras un envío exitoso en una
  conversación que **tenía borrador** (`!escalar`). Sin borrador → no reportes.

### Qué guarda
`AgenteFeedback`: `phone`, `wa_message_id`, `borrador`, `enviado`, `editado`,
`procesado` (lo usará la parte 2), `created_at`. Visible en el admin Django (solo
lectura). Indexado por `created_at`/`editado` para las métricas de la parte 3.

### Activar
1. Deploy (pusheado).
2. Migración en Shell de Render: `python manage.py migrate whatsapp_agent` (0004,
   1 tabla nueva; aditivo).
3. Tu lado empieza a reportar → se acumulan deltas desde ya.

### Validación (Django)
`manage.py check` 0 issues + smoke test (URL `/api/whatsapp/agente/feedback` resuelve)
+ 10/10 tests de lógica.

---

## Parte 2 ⭐ — Clasificar + proponer (siguiente, el corazón)

Plan propuesto (avísame y calzo nombres):
- Modelo `SugerenciaAprendizaje` (`tipo` ∈ {hecho_catalogo, regla, tono, puntual},
  `texto_propuesto`, `borrador`, `enviado`, `phone`, `ref_catalogo` (item/campo/valor
  sugerido, opcional), `estado` ∈ {pendiente, aprobada, descartada}, `created_at`).
- Al llegar feedback con `editado=true` → clasificación LLM **async** que compara
  borrador vs enviado **+ consulta el catálogo en vivo** y rutea:
  `hecho_catalogo` (aprueba Jorge) / `regla` → append a `conocimiento` (H-009a) /
  `tono` / `puntual` (no propone nada).
- Endpoints (luna-key): `GET /api/whatsapp/agente/sugerencias-aprendizaje`,
  `POST .../<id>/aprobar` (acepta `{texto}` editado), `POST .../<id>/descartar`.
- **`hecho_catalogo`: MVP = mostrar el cambio para aplicarlo a mano** (tocar el
  catálogo de ventas toca modelos con drift AR-034); auto-aplicar campos claros
  (precio / `ofrecible_agente`) como mejora posterior, con cuidado.

⚠️ Nota: la parte 2 (hecho_catalogo → catálogo) se apoya en **H-009b** (catálogo rico
+ flag `ofrecible_agente`). Conviene hacer H-009b antes (o junto) para que el
clasificador tenga el valor actual contra el cual comparar y un destino donde rutear.

## Parte 3 — Tablero de evolución
`GET /api/whatsapp/agente/metricas?semanas=8` → serie semanal (semana ISO, TZ Chile)
con `total`, `sin_editar`, `editados`, `pct_sin_editar`. Métrica rey: `pct_sin_editar`.
Sale directo de `AgenteFeedback` (ya indexado por fecha/editado).

Avísame con qué seguimos (2 o H-009b primero) y calzo los contratos.
