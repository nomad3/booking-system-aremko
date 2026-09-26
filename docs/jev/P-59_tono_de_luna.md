# P-59 · Tono de Luna: medirlo cada semana

**Cuándo:** después · **Estado:** espera la re-medición de P-53 (tráfico real
desde el 26-09) · **Escrita:** 26-09-2026 · [Índice](README.md)

## El problema

El 25-09 Jorge preguntó: «¿estás conversando con un robot?». Hoy el tono se
mide contando frases. La línea base de 30 días (P-53):

- el 53% de los borradores empezaba con «Perfecto»;
- el 11% de los mensajes seguidos repetía las tres primeras palabras;
- el 14% decía «te gustaría reservar».

Eso mide muletillas, no si suena a robot. Una Luna que cambie «Perfecto» por
«Genial» pasaría la prueba y seguiría sonando igual.

## La pregunta para Jev

Se le muestra un borrador de Luna (lo que escribió ella, antes de Deborah) y
los cuatro mensajes anteriores de la conversación.

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿Cómo suena? | `choice` | natural · correcto pero rígido · a robot |
| ¿Por qué? | `choice` | empieza igual que el mensaje anterior · muletilla · no responde lo que preguntaron · demasiado largo · parece formulario · nada |

## Qué hace el sistema con la respuesta

Nada en la conversación: **es un termómetro, no un freno.** Cada semana toma
100 borradores al azar y deja un número (qué porcentaje suena a robot, y por
qué) en las métricas de Luna, junto al porcentaje de borradores que Deborah
envía sin editar.

## Quién revisa lo dudoso

- **Jorge calibra antes de usarlo:** lee 40 borradores ya etiquetados por Jev.
  Si no coincide con su criterio en 8 de cada 10, no sirve, y se queda el
  conteo de frases.
- Después, cada semana, los 5 borradores con peor nota van a Jorge, para ver
  qué corregir.

## Cómo sabremos si sirvió

- Coincide con Jorge.
- **El número se mueve cuando el tono cambia.** Por ejemplo, entre los
  borradores de antes y de después de los cambios del 25-09.

## Costo

100 borradores a la semana: menos de un centavo de dólar al mes.

## Qué medir antes de empezar

La re-medición de P-53 con tráfico desde el 26-09: las tres cifras de arriba y
el silencio después de un «hola» solo (17% tras el saludo contra 30% tras la
carta). Es la vara contra la que se compara a Jev.

## Para quien lo construya

- Los borradores y lo que envió Deborah están en `AgenteFeedback` (campos
  `borrador` y `enviado`).
- Las métricas de Luna salen de `/api/metrics/agente`
  (`ventas/views/metrics_api_views.py`, H-021), que ya calcula el porcentaje sin
  editar por semana.
- Es subjetivo: no está probado que Jev sirva para juzgar estilo. Por eso la
  calibración con Jorge va primero y puede terminar en «no».
