# P-61 · El control antes de que Luna responda sola

**Cuándo:** al final · **Estado:** solo se construye el día que Luna pase de
`borrador` a `auto_info` · **Escrita:** 26-09-2026 · [Índice](README.md)

## El problema

Hoy todo lo que escribe Luna pasa por Deborah (modo `borrador`). Para que Luna
conteste sola lo informativo (horarios, precios, cómo llegar) hace falta un
control que frene lo que no debería salir. Es el proyecto más valioso a largo
plazo: libera a Deborah de lo repetitivo.

**Pero hoy restaría, y el encargo del aprendizaje lo dice explícito:**

- En modo borrador, un control que desconfía le quita el borrador a Deborah y
  la obliga a escribir de cero.
- El estudio de primeras respuestas (P-34) mostró que lo que separa una
  conversación que cotiza de una que muere es **la concretud**, no la velocidad
  ni el largo. Un control mal calibrado frena justo las respuestas concretas.

Por eso va al final, cuando la bandeja (P-55) y el aprendizaje (P-54) hayan
mostrado cuánto se puede confiar en Jev con los datos de Aremko.

## La pregunta para Jev

Se le muestran la conversación y el borrador de Luna.

| Pregunta | Tipo | Opciones |
|---|---|---|
| ¿El borrador solo informa, sin comprometer una reserva, un pago, un cambio ni una excepción? | `noul` | probabilidad de que sí, de 0 a 1 |
| ¿Responde lo que el cliente preguntó? | `noul` | probabilidad de que sí, de 0 a 1 |
| ¿Ofrece algo que no existe (un servicio, una hora o un precio fuera del catálogo)? | `noul` | probabilidad de que sí, de 0 a 1 |

Se suma a los frenos que ya están en el código, como el que impide ofrecer una
hora que no existe. No los reemplaza.

## Qué hace el sistema con la respuesta

El mensaje sale solo únicamente si Jev está seguro de las tres: 0,90 o más de
que solo informa y de que responde lo preguntado, y 0,10 o menos de que ofrezca
algo que no existe. Si no, queda como borrador para Deborah, como hoy. **Nunca
bloquea:** en el peor caso, Deborah lo ve, que es lo normal hoy.

## Quién revisa lo dudoso

Deborah, en la bandeja, como hoy.

## Cómo sabremos si sirvió

- Jorge lee cada semana una muestra de los mensajes que salieron solos:
  **cero datos equivocados**.
- Qué porcentaje de mensajes sale solo, y cuánto baja el tiempo de primera
  respuesta.

## Costo

Luna escribe unos 3.000 borradores al mes (3.046 en 30 días, medido el
25-09-2026). Con tres preguntas cada uno, menos de un dólar al mes. Suma unos
0,2 segundos a cada respuesta.

## Qué medir antes de empezar

1. **Qué borradores envía Deborah sin editar, por tipo de pregunta.** En total
   ya se sabe: de 3.046 en 30 días editó 1.245, así que **el 59% sale tal
   cual** (medido el 25-09). Ese es el techo de lo que podría salir solo. La
   curva semanal está en las métricas de Luna (H-021).
2. De los que salen tal cual, cuántos son solo información.
3. Cómo les fue a P-55 y P-54: si Jev acertó con los datos de Aremko.

## Para quien lo construya

- `WhatsAppAgentConfig.modo` tiene las opciones `borrador` y `auto_info`. **En
  Django, `auto_info` hoy es solo una opción**: ningún código la implementa
  (revisado el 26-09-2026). Falta revisar qué hace aremko-cli con ella.
- El control iría en el turno de Luna (`whatsapp_agent/agent.py`), después de
  generar el borrador y antes de decidir si sale.
- La advertencia completa está en el encargo del aprendizaje
  (`PROMPT_JEV_AREMKO.md`, sección «Qué NO hay que construir»).
