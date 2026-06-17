# BRIEF H-022 — Métricas: drill-down de reservas atribuidas + funnel por semana

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-16
**Lado que implementa:** Django (endpoints) + aremko-cli (UI)
**Contexto:** sobre el módulo de métricas H-021 (Tablero de Evolución).

## Pedido de Jorge (mirando el bloque "Campañas")
Viendo "3 reservas / $138.000", quiere **transparencia**: listar las reservas
atribuidas con **cliente, número de reserva, servicios incluidos (cantidad y
valor), fecha y total**. Y que el selector de tiempo permita ver los datos de
**una semana puntual** (no solo la ventana de N semanas).

## 1) Nuevo endpoint — detalle de reservas atribuidas
```
GET /api/metrics/campanas/reservas?weeks=12&semana=2026-W22   (X-API-Key)
```
- `semana` opcional: si viene, solo las reservas atribuidas en esa semana ISO;
  si no, todas las del rango `weeks`.
- Devuelve el detalle de cada `ContactoWhatsApp.reserva_atribuida` (la `VentaReserva`):
```json
{
  "reservas": [
    {
      "venta_id": 4521,
      "cliente_nombre": "María González",
      "fecha_reserva": "2026-05-30",          // fecha de la reserva/servicio
      "fecha_atribucion": "2026-05-28",        // cuándo se atribuyó (envío→reserva)
      "total": 110000,
      "servicios": [
        {"nombre": "Tina Hidromasaje Llaima", "cantidad": 2, "valor": 100000},
        {"nombre": "Desayuno", "cantidad": 1, "valor": 10000}
      ]
    }
  ],
  "total_reservas": 3,
  "total_ingreso": 138000
}
```
- `servicios` = los `ReservaServicio`/`ReservaProducto` de esa venta (nombre +
  cantidad + valor de línea). Como prefieras estructurarlo; lo importante es que
  Jorge vea **qué se reservó, cuánto y cuándo**.
- Esto le permite **verificar la atribución** (¿la reserva realmente vino de la
  campaña o es coincidencia dentro de los 30 días?).

## 2) Funnel por semana — agregar `generados` y `aprobados` a la serie
Hoy `/api/metrics/campanas` → `series[{semana, enviados, costo, respondieron, reservaron, ingreso}]`.
Para mostrar el **funnel completo de una semana puntual**, agregar a cada fila de
la serie también **`generados`** y **`aprobados`**:
```json
{"semana":"2026-W22","generados":80,"aprobados":42,"enviados":40,"costo":3000,
 "respondieron":12,"reservaron":3,"ingreso":110000}
```
Así el front, al elegir una semana, arma el funnel de esa semana desde la serie
(sin endpoint extra) y trae el detalle de reservas con `?semana=`.

## aremko-cli (lo construye en este ciclo)
- Proxy Go `GET /api/v1/metrics/campanas/reservas?weeks=&semana=`.
- En el bloque Campañas: selector de **semana** (poblado desde la serie) +
  "Todo el período". Al elegir una semana → el funnel/KPIs reflejan esa semana
  (de la serie) y se lista el detalle de reservas de esa semana.
- Tabla de reservas: cliente · nº reserva · servicios (cant × valor) · fecha · total.

## Notas
- Sin migración (todo lectura sobre `ContactoWhatsApp`/`VentaReserva`/`ReservaServicio`).
- Confirmar/dejar documentada la **regla de atribución** exacta (qué hace que una
  `VentaReserva` quede como `reserva_atribuida` de un `ContactoWhatsApp`: ventana
  30 d post-envío, match por cliente/teléfono) para mostrarla como tooltip si querés.
