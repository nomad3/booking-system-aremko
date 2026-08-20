# Estudio de reservas (BD producción, solo lectura) — corrida 2026-08-20

Salida de `analysis/estudio_reservas_bd.py` ejecutado en el shell de Render.
Datos 100% agregados, sin información personal. Ventana: últimos 24 meses
(desde 2024-08-20). Servicios reservados en la ventana: **12.352**.

> Nota de calidad de datos: el tipo `otro` incluye filas `Descuento_Servicios`
> cuyo campo `cantidad_personas` contiene montos de descuento (valores de
> cientos de miles) y revenue negativo. Ese tipo se EXCLUYE del análisis de
> motivos; tinas/masajes/cabañas están limpios.

## 1. Reservas por tipo de servicio y mes (extracto: tinas/masajes/cabañas)

| año-mes | cabana | masaje | tina |
|---|---|---|---|
| 2024-10 | 35 | 117 | 140 |
| 2024-11 | 61 | 175 | 200 |
| 2024-12 | 57 | 159 | 182 |
| 2025-01 | 72 | 169 | 218 |
| 2025-02 | 98 | 312 | 380 |
| 2025-03 | 48 | 148 | 195 |
| 2025-04 | 40 | 121 | 154 |
| 2025-05 | 44 | 192 | 216 |
| 2025-06 | 36 | 139 | 183 |
| 2025-07 | 38 | 148 | 209 |
| 2025-08 | 55 | 157 | 208 |
| 2025-09 | 28 | 111 | 142 |
| 2025-10 | 47 | 148 | 177 |
| 2025-11 | 41 | 124 | 141 |
| 2025-12 | 54 | 146 | 183 |
| 2026-01 | 59 | 220 | 212 |
| 2026-02 | 100 | 273 | 344 |
| 2026-03 | 56 | 233 | 225 |
| 2026-04 | 31 | 108 | 127 |
| 2026-05 | 46 | 163 | 193 |
| 2026-06 | 40 | 124 | 140 |
| 2026-07 | 49 | 189 | 205 |
| 2026-08* | 38 | 114 | 121 |

\* mes parcial (corte 20-ago). Revenue mensual estimado del trío en meses
normales: $20-28M CLP; peak febrero: $41-43M CLP.

## 2. Anticipación de reserva (días entre compra y servicio)

| tipo | n | mismo día | ≤1 día | ≤7 días | ≤30 días | mediana | p75 | p90 |
|---|---|---|---|---|---|---|---|---|
| cabana | 1.172 | 15.8% | 30.5% | 64.2% | 91.0% | 4d | 12d | 26d |
| masaje | 3.790 | 25.3% | 45.5% | 79.0% | 93.8% | 2d | 6d | 19d |
| tina | 4.488 | 31.8% | 52.1% | 82.1% | 94.9% | 1d | 5d | 15d |

## 3. Día de semana y hora

| tipo | lun | mar | mié | jue | vie | sáb | dom |
|---|---|---|---|---|---|---|---|
| cabana | 8.8% | 5.9% | 9.8% | 11.2% | 21.9% | 31.6% | 10.8% |
| masaje | 8.2% | 4.5% | 11.2% | 11.7% | 16.3% | 29.0% | 19.1% |
| tina | 8.6% | 5.1% | 10.7% | 10.8% | 17.0% | 29.8% | 18.0% |

Horas top — tina: 14h (1.929), 19h (859), 16h, 17h, 21h (285) ·
masaje: 14h (1.288), 18h, 16h, 19h, 15h · cabaña: 16h (677), 14h (373).

## 4. Top servicios (últimos 12 meses)

| servicio | tipo | reservas 12m |
|---|---|---|
| Masaje Relajación o Descontracturante | masaje | 1.895 |
| Tina Hornopiren | tina | 412 |
| Tina Hidromasaje Villarrica | tina | 388 |
| Tina Tronador | tina | 347 |
| Tina Hidromasaje Puntiagudo | tina | 322 |
| Tina Hidromasaje Llaima | tina | 279 |
| Tina Calbuco (grupal) | tina | 193 |
| Cabaña Laurel | cabana | 142 |
| Cabaña Acantilado | cabana | 141 |
| Tina Osorno (grupal) | tina | 128 |
| Tina Normal Niño | tina | 124 |
| Cabaña Torre | cabana | 106 |
| Cabaña Tepa | cabana | 100 |
| Cabaña Arrayan | cabana | 99 |
| Ambientación romántica R1 | otro | 50 |
| Masaje Piedras Calientes | masaje | 43 |
| San Valentin 2026 | otro | 35 |
| Masaje Tui-Na (Nuevo) | masaje | 25 |
| Drenaje Linfático | masaje | 23 |

## 5. Proxy de canal

- Pagos registrados por staff (proxy admin/WhatsApp): **96.6%** de 7.949 pagos.
- Ventas nacidas del checkout web comprobado (PendingReservation): **125 de
  6.117 (2.0%)**.
- Pagos "web" (flow/webpay/MP): entre 20 y 170/mes, sin tendencia clara;
  el grueso siempre es manual.

**Conclusión: el negocio se cierra por WhatsApp/recepción, no por el carrito.**
La métrica primaria de los micrositios debe ser conversaciones WhatsApp, no
transacciones del carrito.

## 6. ¿Cómo se enteró? (encuesta post-visita, n=634)

| canal declarado | n | % |
|---|---|---|
| instagram | 200 | 31.5% |
| soy_cliente | 156 | 24.6% |
| recomendacion | 144 | 22.7% |
| google | 89 | 14.0% |
| otro | 23 | 3.6% |
| facebook | 19 | 3.0% |
| publicidad | 3 | 0.5% |

## 7. RefugioLead por UTM

18 leads totales: 13 sin UTM, 5 facebook/`refugio_lanzamiento_junio`.
Todos en status `nuevo`.

## 8. Gift cards emitidas por mes (picos)

Diciembre 2024: **79** ($6.8M) · Diciembre 2025: **73** ($5.3M) ·
Mayo 2026: **42** ($3.5M) · Noviembre 2025: **37** · Mayo 2025: **34**.
Meses valle: 6-17/mes. Estacionalidad de regalo clarísima: Navidad >
Día de la Madre > cierre de año.

## Estado de las fuentes de Ads en esta corrida

- **Google Ads**: error 404 HTML — la versión de API por defecto (v21) fue
  retirada por Google. Las credenciales SÍ están operativas (el intercambio
  OAuth funcionó). Corrección: reintentar con `GOOGLE_ADS_API_VERSION`
  más nueva (el script `export_ads.py` ahora la detecta automáticamente).
- **Meta Ads**: el listado de campañas salió completo (útil para clasificar
  motivos por nombre de campaña), pero las métricas llegaron en cero porque
  el campo `insights{}` sin rango usa una ventana por defecto sin gasto
  reciente. Corrección: el script ahora pide insights lifetime
  (`date_preset=maximum`) a nivel campaña.
