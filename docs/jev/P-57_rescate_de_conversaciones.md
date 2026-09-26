# P-57 · Rescate de conversaciones que mueren después del precio

**Cuándo:** después · **Estado:** antes, re-medir el efecto de la carta (P-34a)
· **Escrita:** 26-09-2026 · [Índice](README.md)

## El problema

- **El 88% de las conversaciones de WhatsApp nunca llega a cotizar** (embudo,
  P-30 y P-31).
- De las que no cotizan, **el 52% (unas 249 al mes) muere después de recibir
  precio o información**: la categoría `silencio_tras_info`, medida en agosto
  de 2026.
- No es falta de respuesta: en 60 días, de 1.655 teléfonos que no recibieron
  cotización, **solo 2 quedaron sin respuesta nuestra**. Contestamos, el cliente
  conversa y después se apaga.

Lo que ya existe:

- **La carta de precios** (en producción desde el 20-08, P-34) ataca a este
  mismo grupo. Su efecto no se ha re-medido.
- **Los recordatorios de Luna** (H-109) empujan tres momentos: una cotización
  sin respuesta, una cotización por vencer y una reserva sin pago. Ninguno
  cubre al que **nunca llegó a cotizar**: ahí está el hueco.

## La pregunta para Jev

Se le muestra la conversación completa.

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿Mostró interés concreto (fecha, personas o servicio) y quedó sin decidir? | `choice` sí/no | sí · no |
| ¿Qué lo frena? | `choice` | precio · fecha u horario · tiene que consultarlo · no se sabe |
| ¿Qué seguimiento le sirve? | `choice` | recordarle su fecha · una alternativa más económica · otra fecha u hora · gift card, si es para regalar · ninguno |

## Qué hace el sistema con la respuesta

- Propone el seguimiento **como borrador para Deborah**, igual que los de Luna.
  Nunca envía solo.
- **Dentro de la ventana de 24 horas de WhatsApp**, que es gratis: después de
  unas horas de silencio y antes de que se cierre (el mismo criterio de los
  recordatorios). Fuera de la ventana solo se puede con una plantilla pagada.
- El texto lo arma el código según la opción elegida, como los recordatorios.
  No lo inventa un modelo.
- A quien dijo que no, no se le escribe.

## Quién revisa lo dudoso

Deborah aprueba cada seguimiento. Con confianza bajo 0,70 no se propone nada.

## Cómo sabremos si sirvió

**Mitad con seguimiento y mitad sin**, al azar, durante un mes. Se compara qué
porcentaje vuelve a escribir y qué porcentaje cotiza. Sin grupo de comparación,
cualquier fin de semana largo parece un éxito.

## Costo

Unas 249 conversaciones al mes: menos de un centavo de dólar.

## Qué medir antes de empezar

1. **El P-34a:** si la carta de precios ya bajó `silencio_tras_info`. Si bajó
   mucho, el proyecto se achica.
2. **Leer 30 a 50 conversaciones muertas** y ver si el motivo se puede saber.
   Si casi siempre «no se sabe», Jev no puede elegir un seguimiento y el
   proyecto no va.
3. Cuántas mueren **dentro** de la ventana de 24 horas, que se pueden rescatar
   gratis, y cuántas fuera.

## Para quien lo construya

- El motivo ya lo clasifica `whatsapp_agent/temas.py` (P-31, 11 categorías) con
  un modelo que escribe. Jev podría reemplazarlo: más barato y con confianza.
- El patrón para enviar ya está hecho en `RecordatorioLuna` (H-109): Django
  decide y deja la bitácora, el Go envía y se revalida la ventana de 24 horas.
- Relacionado: P-34 (a y b) en `docs/PENDIENTES.md`.
