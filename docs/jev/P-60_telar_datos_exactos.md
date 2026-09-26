# P-60 · Telar: que una pieza no contradiga los datos del negocio

**Cuándo:** después · **Estado:** se construye en Datamatic, no en este
repositorio · **Escrita:** 26-09-2026 · [Índice](README.md)

## El problema

Telar (el asistente de publicaciones) vive en Datamatic desde agosto, y Aremko
lo usa como cliente. Su revisor tiene dos capas:

1. **Chequeos fijos:** frases prohibidas, largo por canal, llamada a la acción,
   hashtags y si la pieza dice algo que solo este negocio puede decir (P-87).
2. **Revisión visual con Claude Sonnet:** encuadre, luz, legibilidad y formato.

**Ninguna compara lo que la pieza afirma contra los datos exactos del
negocio.** El 15-09-2026 una historia de Aremko invitaba a venir un martes, y
Aremko cierra los martes. El dato estaba escrito y el modelo lo ignoró. Se
arregló con un candado fijo **solo para el día cerrado** (P-108 de Datamatic).
El resto de los datos exactos no tiene candado: los 38° del agua, los 50
minutos del masaje, los precios y los horarios.

## La pregunta para Jev

Se le muestran el texto de la pieza y los datos exactos del negocio.

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿La pieza afirma algo que contradice los datos exactos? | `choice` sí/no | sí · no |
| ¿Qué dato? | `choice` | precio · día u horario · duración · temperatura · un servicio que no existe · ninguno |

## Qué hace el sistema con la respuesta

Agrega una observación al revisor, por ejemplo «la pieza dice 60 minutos y el
masaje dura 50». **No bloquea ni cambia nada:** la regla de oro de Telar es que
el revisor aconseja y una persona decide.

## Quién revisa lo dudoso

Quien aprueba la pieza, como hoy.

## Cómo sabremos si sirvió

En una corrida en seco sobre las piezas de los últimos dos meses, **encuentra
los errores reales que se corrigieron a mano**, con pocas falsas alarmas (una
de cada diez como máximo).

## Costo

Decenas de piezas a la semana: centavos de dólar.

## Qué medir antes de empezar

**Cuántas piezas de los últimos dos meses traían un dato equivocado**, ya sea
publicadas o corregidas antes de publicar. Si fuera del martes casi no hay
casos, el proyecto no vale la pena.

## Para quien lo construya

- En Datamatic: `apps/publicaciones/revisor.py` (las dos capas),
  `cerrado.py` (P-108), `genericidad.py` (P-87) y `diferencia.py` (P-72, lo que
  no se puede afirmar). `apps/decisiones/decidir.py` ya existe allá.
- Cuando le toque, se abre como pendiente de Datamatic: sirve para todos los
  clientes de Telar, no solo para Aremko.
