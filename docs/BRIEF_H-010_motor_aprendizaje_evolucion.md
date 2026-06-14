# BRIEF H-010 — Motor de aprendizaje del agente + indicadores de evolución

- **Solicita:** agente aremko-cli (a pedido de Jorge)
- **Implementa:** Django (almacenamiento + clasificación + métricas) + aremko-cli (captura + UI + tablero)
- **Fecha:** 2026-06-14
- **Estado:** SOLICITADO
- **Propósito:** el agente (H-007) mejora **progresivamente** aprendiendo de las correcciones de Deborah,
  y la mejora se VE como tendencia (película), no foto. El agente **orienta/acompaña/resuelve** (no solo
  vende). Motor de mejora = **delta entre el borrador propuesto y lo que Deborah realmente envía**.

## Principio: el agente aprende solo, pero confirma antes de grabar — y NO memoriza hechos

1. El agente propone un borrador → Deborah edita/envía → capturamos el **delta**.
2. Si hubo edición, el agente **clasifica** la corrección y **propone la acción en el lugar correcto**.
3. Un humano la **aprueba con un clic** (Deborah NO tiene que saber a dónde va el cambio).
4. El agente mejora → Deborah edita menos → la curva sube.

> **Distinción CLAVE (hechos vs reglas):**
> - **Hechos dinámicos** (precios, ofertas/packs, disponibilidad, productos/servicios nuevos o
>   descontinuados, vendible vs doméstico) → viven en el **CATÁLOGO/BD**, el agente los lee **EN VIVO**.
>   El agente **nunca memoriza un precio** (quedaría viejo). Esto es la Fase 2(b) (H-009b): catálogo rico
>   + flag `ofrecible_agente`.
> - **Reglas/políticas estables** (es por persona, qué se reserva online, tono) → bloque **Conocimiento**.
> Mismo patrón validado: *el agente propone, un humano aprueba.* NO auto-escribe sin aprobación.
> Encender la captura YA (no perder semanas de datos).

---

## PARTE 1 — Captura del delta (EMPEZAR ACÁ, base de todo)

**Django:** modelo `AgenteFeedback` + endpoint:
```
POST /api/whatsapp/agente/feedback   (luna-key)
body: { phone, wa_message_id, borrador, enviado, editado:bool }  → { ok: true }
```
Guardar ambos textos + flags + created_at. Fire-and-forget (no rompe el envío).

**aremko-cli (yo):** tras envío exitoso en conversación que **tenía borrador** (`!escalar`), reporto el
evento (proxy Go). `editado = enviado.trim() !== borrador.trim()`. Sin borrador → no reporto.

## PARTE 2 — El agente CLASIFICA la corrección y propone la acción correcta (auto-aprendizaje + aprobación) ⭐

El corazón. **Deborah NO decide a dónde va el cambio** — solo edita/envía natural. Cuando hubo edición,
el agente **compara borrador vs enviado + consulta el catálogo en vivo**, **clasifica** y propone la
acción en su lugar, para aprobar con un clic.

**Clasificación (LLM, async):**

| `tipo` | señal | destino al aprobar | aprueba |
|---|---|---|---|
| `hecho_catalogo` | cambió precio/disponibilidad/existencia; difiere del catálogo | actualizar catálogo (precio / flag `ofrecible_agente` / dar de baja) | **Jorge** (negocio) |
| `regla` | cambió el *cómo*/política (qué se reserva online, qué ofrecer) | agregar al campo `conocimiento` (H-009a) | Deborah/Jorge |
| `tono` | misma info, redacción más cálida/breve | nota de tono (o nada) | Deborah |
| `puntual`/`ninguno` | específico de ese cliente / typo | **nada** | — |

El LLM compara el hecho corregido contra el catálogo (conoce el valor actual) → así distingue hecho de
regla y hasta apunta al ítem/campo exacto. Si es puntual/typo → no propone nada (no se llena de ruido).

**Django:**
- Modelo `SugerenciaAprendizaje` (tipo, texto_propuesto, borrador, enviado, phone, ref_catalogo?
  (ítem/campo/valor sugerido), estado: pendiente/aprobada/descartada, created_at).
- Al llegar feedback con `editado=true`: LLM async clasifica + propone (o nada).
- Endpoints (luna-key): `GET /api/whatsapp/agente/sugerencias-aprendizaje` (pendientes);
  `POST .../<id>/aprobar` (ejecuta según `tipo`: `regla`→append a `conocimiento`; `hecho_catalogo`→
  **MVP: mostrar el cambio sugerido para que el humano lo aplique en el admin**; one-click-apply de
  campos claros (precio / `ofrecible_agente`) como mejora posterior — con cuidado por drift AR-034);
  `POST .../<id>/descartar`. Aprobar acepta `{texto}` editado.

**aremko-cli (yo):** sección "🧠 El agente aprendió algo" en la página Agente IA: lista de pendientes,
cada una mostrando **qué corrigió Deborah, el `tipo` y el destino**, con **Aprobar / Editar / Descartar**.
Las de `hecho_catalogo` (precio) se marcan "requiere Jorge". El humano puede **redirigir** el tipo si el
clasificador se equivocó.

**Madurez:** al principio todo se aprueba a mano; cuando las métricas muestren clasificación/extracción
buena y consistente, se deja que los casos más seguros fluyan más solos.

## PARTE 3 — Indicadores de evolución (tablero)

**Django:** serie **semanal**:
```
GET /api/whatsapp/agente/metricas?semanas=8   (luna-key)
→ { semanas: [ { semana:"2026-W24", total, sin_editar, editados, pct_sin_editar, escalados? }, ... ] }
```
Métrica rey: `pct_sin_editar` por semana. Complementarias si son fáciles.

**aremko-cli (yo):** tablero "Evolución del agente" (página Agente IA o Tableros) con las curvas semana
a semana → se ve la línea subir y se vincula con las reglas/hechos que se van aprobando.

## Reparto y orden

| # | Qué | Django | aremko-cli |
|---|-----|--------|-----------|
| **1** | Captura del delta | `AgenteFeedback` + `POST /agente/feedback` | reportar en el envío (+ proxy) |
| **2** ⭐ | Clasificar corrección + proponer acción (catálogo/regla/tono) + aprobación | `SugerenciaAprendizaje` + clasificador LLM + endpoints | sección "El agente aprendió algo" + proxies |
| **3** | Tablero de evolución | `GET /agente/metricas` (serie semanal) | tablero de curvas (+ proxy) |

**Orden:** 1 → 2 → 3. (1) base (datos desde ya); (2) corazón (auto-aprendizaje ruteado); (3) lo hace visible.

## Aceptación

- **(1)** Deborah envía borrador tal cual → "sin editar"; lo edita → "editado". Registrado.
- **(2)** Corrige un **precio** → propuesta tipo `hecho_catalogo` ("actualizar Calbuco a $X") para Jorge.
  Corrige una **política** ("deportivo no se reserva online") → propuesta tipo `regla` para el Conocimiento.
  Algo **puntual** (saludo personalizado) → no propone nada.
- **(3)** Tablero muestra `% sin editar` semanal, subiendo a medida que se aprueban correcciones.

## Notas / a tu criterio
- Nombres finales de modelos/campos/endpoints (avísame y calzo aremko-cli).
- Extracción/clasificación: al recibir el feedback, async; sanitizar textos.
- Aplicar cambios al catálogo de ventas (precio/flag) toca modelos con drift AR-034 → MVP "mostrar para
  aplicar a mano", auto-aplicar después con cuidado.
- Semana ISO, zona horaria Chile.

## Punteros
- Conocimiento (`conocimiento`): H-009a. Catálogo rico + flag: H-009b. App `whatsapp_agent`.
- Origen del dato (aremko-cli): flujo de `reply` + `sugerencia_agente`.
