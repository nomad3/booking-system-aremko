# P-56 · Pagos y transferencias: decidir los dudosos del Conciliador

**Cuándo:** primero · **Estado:** espera una respuesta de Deborah (P-23) ·
**Escrita:** 26-09-2026 · [Índice](README.md)

## El problema

El Conciliador (en producción desde el 06-07-2026) trae los pagos de Mercado
Pago y los calza con reglas fijas, en orden: referencia externa, número de
reserva en la glosa, saldo exacto, total exacto, abono del 50% y, si quedan
varias candidatas, el nombre del cliente en la glosa. Si una sola reserva
calza, queda **sugerido** y Deborah confirma con un clic. Si calzan varias o
ninguna, queda en **revisar** y Deborah lo busca a mano. Nada se aplica
solo: activar el auto-aplicar (P-07) está pendiente desde julio.

Y hay una pregunta abierta que pesa más que Jev: **en julio, el 76% de la plata
(140 movimientos, $16,4M de $21,5M) terminó en «ignorado»**. No sabemos si
Deborah quiere decir «ya lo registré a mano» o «no sé qué hacer con él» (P-23).

## La pregunta para Jev

Solo para los movimientos en **revisar**. Se le muestra el pago (monto, fecha,
glosa) y las reservas candidatas, de 2 a 5 (cliente, total, saldo, fecha,
abonos anteriores). Las opciones se arman en cada llamada:

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿A qué reserva corresponde este pago? | `choice` | una opción por reserva candidata · ninguna de estas |

## Qué hace el sistema con la respuesta

1. **Primera etapa: sugiere.** La reserva que eligió Jev aparece junto al
   movimiento, con su confianza, y Deborah aplica con un clic, igual que hoy
   con los sugeridos.
2. **Segunda etapa, solo si acierta: esto es el P-07.** Se aplica solo cuando
   la regla fija y Jev eligen la misma reserva, con confianza de 0,90 o más.
   El candado de hoy se mantiene: nunca a una reserva sin saldo.

## Quién revisa lo dudoso

Deborah, como hoy. Con confianza bajo 0,70, Jev no sugiere nada.

## Cómo sabremos si sirvió

- En dos semanas de sugerencias, **Deborah acepta 9 de cada 10 sin cambiarlas**.
- Baja la cola de «revisar».
- Deborah dice cuántas horas a la semana le ahorra.

## Costo

En julio hubo unos 400 movimientos, y solo los dudosos pasan por Jev: menos de
un centavo de dólar al mes.

## Qué medir antes de empezar

1. **Responder el P-23 con Deborah.** Si «ignorar» quiere decir «ya lo
   registré a mano», el problema es otro: el Conciliador llega tarde, y Jev no
   lo arregla. Si quiere decir «no sé qué hacer», hay pagos sin aplicar y este
   proyecto vale.
2. Cuántos movimientos quedan en «revisar» al mes y cuántos resuelve bien cada
   regla fija.
3. Una muestra de 30 «revisar» que Deborah ya resolvió, para probar a Jev en
   seco contra su decisión.

## Para quien lo construya

- App `conciliacion`: modelo `MovimientoMP` (estados sugerido, revisar,
  aplicado e ignorado), las reglas en `matchear_movimiento()` de
  `conciliacion/services_mp.py` y el admin «Movimientos Mercado Pago». Jev
  entra donde hoy termina en `'revisar'`.
- Relacionado: P-07 (auto-aplicar), P-08 (limpiar la tanda histórica) y P-23 (qué
  significa «ignorar»), en la sección *Pagos y conciliador* de
  `docs/PENDIENTES.md`.
