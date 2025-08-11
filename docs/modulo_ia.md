## Módulo IA – Diseño funcional y técnico (Fase 1)

Autor: Equipo Aremko · Estado: Propuesto · Alcance: Fase 1 (MVP)

### Objetivo
Incorporar capacidades de Inteligencia Artificial que aumenten ingresos, ocupación y satisfacción del cliente, y reduzcan carga operativa. La Fase 1 prioriza tres capacidades de alto impacto y bajo riesgo.

### Alcance Fase 1 (MVP)
1) Chat IA de Negocio (Deepseek)
   - Consultas en lenguaje natural a la base de datos en modo solo lectura.
   - Responde con tablas/resúmenes y explicaciones. Exportable a CSV.
   - Ejemplos:
     - “Top 10 clientes 2025 por total pagado”
     - “Ocupación de cabañas el próximo fin de semana”
     - “Servicios más vendidos por trimestre 2025”

2) Recomendaciones por Cliente (Next Best Offer)
   - En la ficha de `Cliente`, panel “Sugerencias IA”.
   - Propone: paquetes, add-ons, upgrades y copy de contacto listo para email/SMS.
   - Basado en RFM, afinidades de servicios y estacionalidad.

3) Copiloto de Campañas (Email/SMS)
   - Redacción automática con tono Aremko, variables dinámicas y segmentación sugerida.
   - Compatible con límites anti-spam y preferencias de contacto existentes.

### Métricas de éxito (Fase 1)
- Conversión de campañas IA vs. manuales (+X%).
- Tasa de upsell/cross-sell en recomendaciones (+X%).
- Ahorro de tiempo en generación de reportes y copys (–X%).

---

### Arquitectura propuesta
- Backend Django como orquestador.
- LLM: Deepseek API (server-side) con “tool calling”.
- Tool 1: `query_sql_readonly`
  - Ejecuta SQL plantillado/whitelisteado con parámetros validados.
  - Límite de filas configurable y tiempos de consulta acotados.
- Tool 2: `get_kpi`
  - Consulta KPIs pre-agregados (materialized views o vistas ORM) para respuestas rápidas y baratas.
- Capa de seguridad
  - Solo lectura; bloqueo de `INSERT/UPDATE/DELETE`.
  - Whitelist de plantillas SQL con “named params”.
  - Sanitización de entrada, límites de filas y tiempo, y auditoría por usuario.
  - Registro de costo por interacción (tokens/CLP) y cuotas diarias.
- Observabilidad
  - Logs estructurados: pregunta, plantilla usada, parámetros, duración, costo, filas devueltas.

Diagrama lógico (simplificado)
Usuario → UI Botón IA → Backend Django → (Validator + Router) → Tool SQL Readonly / KPIs → BD (ro) → Respuesta → LLM (formatea y explica) → UI

---

### Seguridad, privacidad y cumplimiento
- Datos mínimos en el prompt; evitar PII innecesaria.
- No se almacenan datos en el proveedor del LLM (sin fine-tuning con datos reales).
- Seudonimización de identificadores cuando sea posible.
- Respeto de preferencias de clientes (opt-out) en cualquier salida que derive en contacto.
- Controles de acceso por rol.

---

### Datos y features (base para IA)
- RFM: Recency (último servicio), Frequency (número de reservas/servicios), Monetary (total pagado).
- Afinidades: co-ocurrencia de servicios reservados (ej. tina + masaje).
- Respuesta a canales: apertura/clic de emails, respuesta a SMS (cuando esté activo), conversión post-envío.
- Estacionalidad y horas valle para propuestas de promos.

Se recomienda crear vistas/materialized views para acelerar consultas frecuentes:
- `vw_clientes_rfm`
- `vw_ventas_anuales`
- `vw_ocupacion_servicios`
- `vw_afinidades_servicios`

---

### UI/UX (Fase 1)
- Nuevo menú “IA” en el dashboard.
  - Submódulos: “Chat de negocio”, “Campañas IA”.
- Ficha `Cliente`: panel “Sugerencias IA”.
- Resultados del chat: tabla + explicación + botón “Exportar CSV”.
- Historial de consultas por usuario con re-ejecución rápida.

---

### Variables de entorno (Fase 1)
- `AI_FEATURES_ENABLED=true`
- `DEEPSEEK_API_KEY=********`
- `AI_SQL_ROW_LIMIT=1000` (límite filas por consulta)
- `AI_MAX_TOKENS=2048`
- `AI_DAILY_COST_LIMIT_CLP=5000` (tope presupuestario por día)
- `AI_ALLOWED_ROLES=admin,marketing` (acceso a Chat/Campañas)
- `AI_LOG_RETENTION_DAYS=30`

---

### Permisos y roles
- `admin`: acceso total a IA.
- `marketing`: Chat de negocio y Campañas IA.
- `recepcion`: sin acceso en Fase 1 (opcional habilitar solo “Sugerencias IA” de cliente).

---

### Plantillas SQL canónicas (para whitelist)
Nota: ajustar a los nombres reales de tablas. Por convención Django, podrían ser:
`ventas_cliente`, `ventas_ventareserva`, `ventas_reservaservicio`, `ventas_pago`.

1) Top 10 clientes 2025 por total pagado
```
SELECT c.id, c.nombre, c.telefono,
       SUM(p.monto) AS total_pagado
FROM ventas_cliente c
JOIN ventas_ventareserva vr ON vr.cliente_id = c.id
JOIN ventas_pago p ON p.venta_reserva_id = vr.id
WHERE DATE_PART('year', p.fecha_pago) = 2025
GROUP BY c.id, c.nombre, c.telefono
ORDER BY total_pagado DESC
LIMIT 10;
```

2) Ocupación por servicio (próximos 14 días)
```
SELECT rs.servicio_id,
       rs.fecha_agendamiento,
       COUNT(*) AS reservas
FROM ventas_reservaservicio rs
WHERE rs.fecha_agendamiento BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '14 days'
GROUP BY rs.servicio_id, rs.fecha_agendamiento
ORDER BY rs.fecha_agendamiento ASC;
```

3) Servicios más vendidos por trimestre (2025)
```
SELECT DATE_TRUNC('quarter', rs.fecha_agendamiento) AS trimestre,
       rs.servicio_id,
       COUNT(*) AS cantidad
FROM ventas_reservaservicio rs
WHERE DATE_PART('year', rs.fecha_agendamiento) = 2025
GROUP BY 1, rs.servicio_id
ORDER BY 1 ASC, cantidad DESC;
```

4) RFM básico por cliente (últimos 12 meses)
```
WITH base AS (
  SELECT vr.cliente_id,
         MAX(rs.fecha_agendamiento) AS last_service,
         COUNT(*) AS freq,
         COALESCE(SUM(p.monto), 0) AS monetary
  FROM ventas_ventareserva vr
  LEFT JOIN ventas_reservaservicio rs ON rs.venta_reserva_id = vr.id
  LEFT JOIN ventas_pago p ON p.venta_reserva_id = vr.id
  WHERE rs.fecha_agendamiento >= CURRENT_DATE - INTERVAL '12 months'
  GROUP BY vr.cliente_id
)
SELECT cliente_id,
       CURRENT_DATE - last_service AS recency_days,
       freq,
       monetary
FROM base
ORDER BY monetary DESC;
```

---

### Copiloto de Campañas – flujo
1) Usuario describe objetivo: “reactivar clientes con recencia > 90 días”.
2) IA sugiere segmento (SQL o filtro ORM), incentivo y copy personalizado.
3) Usuario previsualiza (email/SMS), edita y envía con nuestros límites anti-spam.
4) Se registra impacto (envíos, aperturas, clics, conversiones cuando aplique).

---

### Control de costos y auditoría
- Tope diario en CLP y por usuario.
- Cálculo de costo por interacción (tokens) y consolidado por día/mes.
- Log de cada consulta, con plantilla, parámetros, tiempo y filas.

---

### Roadmap Fase 2 (referencial)
- Pronóstico de demanda y horas valle, con propuestas de promos automáticas.
- Score de no-show y churn.
- Insights de encuestas y sentimiento con alertas.
- Recomendadores más avanzados (secuencia de servicios, upgrades de cabaña).

---

### Plan de implementación (Fase 1)
Semana 1
- Backend: módulo IA, integración Deepseek, herramientas `query_sql_readonly` y `get_kpi`.
- Seguridad: whitelist de 10 plantillas SQL + validación de parámetros.
- Variables de entorno y límites de costo.

Semana 2
- UI: botón “IA”, Chat de negocio, panel “Sugerencias IA” en `Cliente`.
- Copiloto de campañas: asistente de copy + segmento sugerido (sin envío masivo automático por defecto).
- Observabilidad: logs estructurados y panel básico de uso/costo.

Listo para producción cuando
- Pruebas de carga y seguridad superadas.
- Costos controlados y trazabilidad habilitada.
- Validación con 2-3 usuarios internos.

---

### Criterios de aceptación (Fase 1)
- Chat IA responde al menos 10 consultas canónicas sin errores ni timeouts (≤ 5s, ≤ 1000 filas).
- Recomendaciones visibles en la ficha de cliente con copy listo para enviar.
- Copiloto genera textos personalizados y segmentación sugerida, respetando límites anti-spam.
- Logs y costos disponibles por día/usuario.

---

### Notas
- Toda referencia a tablas es orientativa; usar los nombres reales del esquema de Aremko.
- El Chat IA no ejecuta escrituras; cualquier acción de envío se realiza desde los módulos existentes (email/SMS) y respeta preferencias y límites.

