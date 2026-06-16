# BRIEF H-021 — Módulo de Métricas / "Tablero de Evolución" (endpoints de agregación)

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-16
**Lado que implementa:** Django (la data vive acá) — endpoints de agregación read-only
**Front:** aremko-cli arma la página "Métricas / Evolución" que los grafica.

## Objetivo
Un tablero que mida la **evolución** (series semanales) de las funcionalidades ya
implementadas, con foco **comercial** (¿la bandeja vende?) y de **gestión** (¿damos
abasto?, ¿el agente IA se paga?). MVP = 4 bloques, todos con data que YA existe.

## Principios
- **Series temporales** (semana a semana), no solo totales. Param `weeks` (default 12).
- Read-only, sin migraciones nuevas si se puede. Header `X-API-Key: LUNA_API_KEY`.
- Redondear; montos en CLP enteros.

## Endpoints propuestos (ajustables; aremko-cli es el consumidor)

### 1) `GET /api/metrics/campanas?weeks=12`  ← incluye COSTO de plantillas
Funnel + ROI de la Bandeja de envíos (`ContactoWhatsApp`).
```json
{
  "resumen": {
    "generados": 220, "aprobados": 180, "enviados": 176,
    "respondieron": 54, "reservaron": 12,
    "ingreso_atribuido": 1240000,      // suma de reserva_atribuida (ventana 30d)
    "costo_estimado": 158400,          // enviados * tarifa_plantilla_clp
    "roi_neto": 1081600,               // ingreso - costo
    "roas": 7.8                        // ingreso / costo
  },
  "tarifa_plantilla_clp": 900,         // tarifa usada (configurable; ver abajo)
  "series": [
    {"semana": "2026-W20", "enviados": 40, "costo": 36000, "respondieron": 12,
     "reservaron": 3, "ingreso": 310000}
  ]
}
```
- **COSTO de plantillas:** `enviados × tarifa_plantilla_clp`. Las `vac_*` son categoría
  *marketing* → cobran por mensaje (las respuestas del agente dentro de 24h son gratis).
- **tarifa_plantilla_clp configurable** (env `WHATSAPP_TEMPLATE_COST_CLP` o campo en
  `WhatsAppAgentConfig`, a tu criterio). Si no está seteada, devolver `costo_estimado: null`
  + `tarifa_plantilla_clp: null` y el front muestra "configurar tarifa". (Fase 2: costo
  real desde la API de facturación/`pricing_analytics` de Meta.)
- `enviados` por día/semana = transiciones a `estado='enviado'` con `fecha_envio`.
- `ingreso` = suma de `reserva_atribuida` (la ventana 30d que ya manejás).

### 2) `GET /api/metrics/agente?weeks=12`  (curva del agente IA, de `AgenteFeedback`)
```json
{
  "resumen": {"pct_sin_editar": 71, "delta_pts_8sem": 13,
              "aprendizajes_aprobados": 24, "tiempo_ahorrado_min_estim": 540},
  "series": [{"semana":"2026-W20","total":80,"sin_editar":46,"pct_sin_editar":58,
              "escalados":9,"pct_escalado":11}]
}
```
- `pct_sin_editar` = borradores enviados sin editar / total con borrador (de `AgenteFeedback.editado`).
- `tiempo_ahorrado_min_estim` = (borradores aceptados) × min/redacción (constante configurable, ej. 2).

### 3) `GET /api/metrics/canales?weeks=12`  (volumen + servicio; WhatsApp + Instagram)
```json
{
  "resumen": {"backlog_actual": 5, "primera_respuesta_mediana_min": 8},
  "series": [{"semana":"2026-W20","whatsapp":160,"instagram":42,
              "primera_respuesta_mediana_min": 9}]
}
```
- Volumen = conversaciones (o entrantes) por canal por semana (de `WhatsAppMessage` +
  `ChannelMessage`/`inbox_omnicanal`).
- `primera_respuesta_mediana_min` = mediana del tiempo entre el entrante y la 1ª salida.
- `backlog_actual` = conversaciones con `requiere_atencion=True` ahora.

### 4) `GET /api/metrics/masajes?weeks=12`  (Conexión-Masajes, `SeguimientoBienestarMasaje`)
```json
{
  "resumen": {"cobertura_pct": 78, "tasa_respuesta_pct": 31},
  "series": [{"semana":"2026-W20","enviados":18,"respondieron":6,"cobertura_pct":80}]
}
```
- `cobertura_pct` = masajes con seguimiento enviado / masajes del período.
- `tasa_respuesta_pct` = respondieron / enviados.

## KPIs del header (los puede derivar el front de los 4 endpoints)
Conversaciones del mes (+Δ), $ atribuido a campañas, % borradores sin editar, 1ª respuesta mediana.

## Alcance MVP / fases
- **MVP (este H-021):** los 4 endpoints con data existente + costo de plantillas por tarifa configurable.
- **Fase 2 (otro H):** atribución inbound conversación→reserva (cruce teléfono, WA; IG sin teléfono es difícil) + costo real de Meta vía API de facturación.

## aremko-cli
Arma la página "Métricas / Evolución" (cinta de KPIs + funnel/ROI + curvas), mismo patrón
que "Campañas Meta", consumiendo estos endpoints vía proxy Go `/api/v1/metrics/*` (agrega
la X-API-Key). El front se puede ir construyendo contra este contrato; tolera campos null.

## Notas
- Si preferís 1 solo endpoint `GET /api/metrics/evolucion` que devuelva los 4 bloques,
  también sirve — decime y aremko-cli consume eso. Lo importante son las series + el costo.
- Sin migración idealmente; la tarifa de plantilla por env/config.
