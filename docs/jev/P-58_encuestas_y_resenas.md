# P-58 · Encuestas y reseñas: que la queja se vea el mismo día

**Cuándo:** después · **Estado:** la regla ya existe y falta llenar un campo; es
el más chico de los siete · **Escrita:** 26-09-2026 · [Índice](README.md)

## El problema

La encuesta post-visita (D+1, `EncuestaSatisfaccion`) guarda notas de 1 a 5, el
NPS y tres textos libres: lo que más gustó, sugerencias y **«¿Hubo algo que te
decepcionó?»**.

Una regla marca la encuesta para seguimiento urgente (`evaluar_followup`) si se
cumple cualquiera de estos tres criterios:

1. NPS de 6 o menos.
2. Una nota de 1 o 2 en tina, masaje, limpieza, atención o experiencia.
3. **Un texto marcado por IA como urgente.**

**El tercero nunca se cumple: el campo `analisis_ia` de la encuesta no lo llena
nadie** (revisado en el código el 26-09-2026). Por ejemplo, un cliente que pone
NPS 9 y escribe «el agua de la tina estaba tibia» no genera seguimiento. Su
queja espera al análisis semanal de los lunes: hasta una semana.

## La pregunta para Jev

Se le muestran los tres textos y las notas.

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿De qué habla? | `choice` | tina · masaje · cabaña · limpieza · atención · precio · reserva o pago · otro · nada que reclamar |
| ¿Es una queja? | `noul` | probabilidad de que sí, de 0 a 1 |
| ¿Qué tan urgente es? | `choice` | baja · media · alta |

`urgencia` va como `choice` para que traiga confianza y calce directo con lo
que la regla ya lee.

## Qué hace el sistema con la respuesta

- **Al llegar la encuesta**, llena `analisis_ia` con el tema, si es queja, la
  urgencia y la confianza. No hay que tocar la regla: si la urgencia es alta,
  la encuesta queda para seguimiento y entra al reporte de seguimientos
  pendientes.
- **Para el P-13 (pedir reseñas en Google):** pedírsela solo a quien quedó
  feliz, con NPS de 9 o 10 y **sin queja escrita**.

## Quién revisa lo dudoso

Jorge o Deborah, en el reporte de seguimientos. Con confianza bajo 0,70 no se
marca nada y todo queda como hoy, para el análisis semanal.

## Cómo sabremos si sirvió

- Jorge lee 30 encuestas ya clasificadas: **acierta en 8 de cada 10 o más**.
- Días entre una queja escrita y el contacto con ese cliente: de hasta una
  semana a el mismo día.

## Costo

Pocas encuestas al mes: centavos de dólar.

## Qué medir antes de empezar

1. Cuántas encuestas llegan al mes y cuántas traen algo escrito en
   «decepción» o «sugerencias».
2. De esas, **cuántas tienen NPS de 7 o más**: son las que hoy se escapan.
3. **Si el reporte de seguimientos corre de verdad todos los días.** En la
   lista de crons figura como «diario (sugerido)». Si nadie lo agenda, marcar
   la encuesta no sirve de nada.

## Para quien lo construya

- `ventas/models.py`: `EncuestaSatisfaccion.evaluar_followup()` y el campo
  `analisis_ia` (JSON), que hoy solo se lee y se muestra en el admin.
- Hoy existen, con un modelo que escribe: el análisis semanal
  (`ventas/services/survey_ai_analyzer.py`, `analyze_surveys_weekly`, los lunes
  a las 9:00) y el reporte `report_pending_followups`.
- Las reseñas de Google y TripAdvisor (`Review`) ya se extraen con IA de una
  captura que Jorge sube de a una, y traen sentimiento: no necesitan a Jev.
- Relacionado: P-13 (máquina de reseñas) en `docs/PENDIENTES.md`.
