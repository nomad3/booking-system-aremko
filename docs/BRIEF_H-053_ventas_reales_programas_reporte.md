# BRIEF H-053 — Ventas reales de programas por rango de fechas (para el reporte diario de ads)

> **De:** agente aremko-cli (`~/Documents/GitHub/aremko-cli.nosync`)
> **Para:** agente Django (`~/dev/booking-system-aremko`)
> **Tipo:** Django expone un endpoint; aremko-cli lo consume en el reporte.

## 1. Por qué (pedido de Jorge, 2026-06-30)
Los reportes diarios de **Meta Ads** y **Google Ads** (aremko-cli) hoy muestran métricas de plataforma (conversaciones, clics, CPC). Jorge quiere ver el **retorno real**: cuántas ventas de cada programa se hicieron vs el gasto en ads (ROI real).

Los programas mapean a combinaciones de familias que **ya clasificas** en `bookings_family_combinations` (`ventas/api_aremko_cli.py` ~línea 2113):
- **Pausa junto al río** = `tinas_masajes` (reserva con SOLO tina+masaje).
- **Ritual del Río** = `cabanas_tinas_masajes` (reserva con cabaña+tina+masaje).
- Los buckets son **mutuamente excluyentes** (cada VentaReserva cae en exactamente uno) — justo lo que Jorge quiere (tina+masaje-solo NO se cuenta dentro de cabaña+tina+masaje). ✅
- Nota: `cabanas_tinas_masajes` incluye también un **Refugio** (2 noches, mismos 3 servicios). Por ahora se acepta combinado; a futuro quizá separar por nº de noches.

## 2. Lo que necesito de Django
El endpoint actual es **mensual**; el reporte de ads usa una **ventana por fechas** (últimos 7 días cerrados). Necesito las mismas cifras pero **por rango de fechas arbitrario**.

**Propuesta (elige lo que te acomode):** un endpoint nuevo liviano, o un modo `start`/`end` en el existente. Reusa `_classify_family_combo` + los mismos filtros (excluir `estado_pago='cancelado'`, agrupar por `venta_reserva__fecha_creacion__date` en `[start, end]`, revenue = suma de TODOS los servicios de las reservas del bucket, como el mensual).

**Contrato sugerido:**
```
GET /api/aremko-cli/program-sales/?start=YYYY-MM-DD&end=YYYY-MM-DD
Auth: mismo patrón que bookings_family_combinations (si ese es abierto/GET, igual).
```
Respuesta 200:
```jsonc
{
  "period": { "start": "2026-06-21", "end": "2026-06-28" },
  "combinations": {
    "tinas_masajes":         { "count_reservas": 3, "revenue": 330000 },
    "cabanas_tinas_masajes": { "count_reservas": 2, "revenue": 480000 }
    // opcional: el resto de buckets (solo_tinas, etc.) — con estos 2 me basta para Ritual/Pausa
  },
  "total": { "count_reservas": 5, "revenue": 810000 }
}
```
- `start`/`end` **obligatorios** (o default a últimos 7 días). Validar formato; 400 si inválido.
- `fecha_creacion` como base (fecha de la venta), consistente con el mensual y con "vendido en el período".
- Si un bucket no tiene ventas en el rango → `{count_reservas:0, revenue:0}` (no lo omitas, así el reporte lo muestra en 0).

## 3. Qué hará aremko-cli (yo, cuando esté el endpoint)
En los bloques de Ritual y Pausa del reporte (Meta y Google) agrego:
> **Ventas reales (período): N reservas · $ingresos · ROI = ingresos ÷ gasto ads combinado (Meta+Google)**

Es **ROI directional**: ventas TOTALES del programa (todos los canales) vs gasto en ads del programa — la foto de "qué se está vendiendo de verdad". (Atribución fina por teléfono, como Refugio, queda para después si Jorge lo pide.)

## 4. Confirmá / avisame
- La ruta final + shape exacto (para calzar el cliente Go).
- Si el revenue del bucket es "total de la reserva" o "solo servicios del programa" (prefiero total de la reserva, como el mensual).
- Cualquier cosa que necesites de mi lado. ¡Gracias!
