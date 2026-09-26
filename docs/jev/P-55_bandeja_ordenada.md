# P-55 · Bandeja ordenada por lo que falta responder

**Cuándo:** primero · **Estado:** listo para medir · **Escrita:** 26-09-2026
· [Índice](README.md)

## El problema

La bandeja pone arriba lo «pendiente», y pendiente significa una sola cosa: la
marca `requiere_atencion`, que se borra al responder o al tocar «marcar
atendido» (H-005 y H-006). La bandeja no sabe si en la conversación quedó algo
sin contestar.

Datamatic tiene la misma lógica y le preguntó a Jev. En 15 conversaciones
reales, Jev contradijo a la bandeja en 5 casos y **Jorge validó que Jev tenía
razón en los 5** (21-09-2026):

- dos figuraban atendidas con una pregunta del cliente sin respuesta;
- un cliente mandó RUT y correo para reservar y nadie le contestó hasta que se
  cerró la ventana de 24 horas de WhatsApp;
- dos figuraban pendientes sin nada que responder.

Hallazgo de fondo: «atendida» se usa como «leída». No está medido en Aremko,
pero la bandeja funciona igual.

## La pregunta para Jev

Se le muestra la **conversación completa** (los últimos 14 mensajes, con quién
dijo qué y cuándo), no el último mensaje. Las cuatro preguntas que ya usa
Datamatic:

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿En qué quedó? | `choice` | espera respuesta · espera al cliente · por pagar · cerrada · perdida · no es cliente |
| ¿Hay algo concreto que Aremko dejó sin responder? | `noul` | probabilidad de que sí, de 0 a 1 |
| ¿Está cerca de convertirse en una reserva pagada? | `noul` | probabilidad de que sí, de 0 a 1 |
| ¿Qué tan pronto hay que contestar? | `score` | puede esperar · hoy · ahora mismo |

## Qué hace el sistema con la respuesta

1. **Primera etapa: solo opina.** Guarda la respuesta en la conversación y la
   muestra como una etiqueta discreta. No cambia el orden ni los pendientes.
   Así está hoy Datamatic.
2. **Segunda etapa, solo si acierta:** ordena la bandeja por lo que falta
   responder y avisa «quedan N horas de la ventana de 24 h y hay algo sin
   responder».

## Quién revisa lo dudoso

Deborah. Con confianza bajo 0,70 no se muestra etiqueta y el orden sigue
siendo el de hoy.

## Cómo sabremos si sirvió

- Una semana comparando la etiqueta contra lo que hizo Deborah. **Si acierta 8
  de cada 10** (la misma vara de Datamatic), se le deja ordenar.
- A la larga: cero conversaciones que se salen de la ventana de 24 horas con
  algo sin responder.

## Costo

En Datamatic, 24 conversaciones costaron US$0,00095 (192 ms de mediana). Aunque
Aremko opine 5.000 veces al mes, son unos US$0,20 al mes.

## Qué medir antes de empezar

1. En los últimos 30 días, **cuántas conversaciones «atendidas» terminan en una
   pregunta del cliente**. Jorge lee una muestra de 30 a 50.
2. Cuántas se salieron de la ventana de 24 horas con algo sin responder.
3. Cuántos mensajes entran al día: cada uno dispara una opinión.

## Para quien lo construya

- En Datamatic está hecho: `apps/mensajeria/inteligencia.py` (`opinar()`, las
  preguntas y el estado) y los campos `ia_*` de la conversación. Se porta casi
  tal cual, con `whatsapp_agent/decisiones.py`.
- En Aremko, el pendiente es la marca `requiere_atencion` de cada mensaje
  entrante. WhatsApp: `ventas/views/whatsapp_api_views.py`, donde también se arma
  la lista con los pendientes primero (H-006). Instagram y Messenger:
  `inbox_omnicanal/views.py`. La etiqueta la muestra aremko-cli.
- La opinión no puede demorar el mensaje entrante: corre después de guardarlo,
  y si falla no pasa nada.
- Relacionado: P-115 de Datamatic (su `docs/PENDIENTES.md`).
