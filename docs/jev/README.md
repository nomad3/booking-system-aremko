# Jev en Aremko

Índice de los proyectos con Jev. Escrito el 26-09-2026, un día después de
instalarlo para el aprendizaje de Luna (P-54). Cada proyecto tiene una ficha de
una página en esta carpeta y una línea en `docs/PENDIENTES.md` (P-55 a P-61).

Las fichas **no son planes**. Dicen qué problema resuelve cada proyecto, con qué
dato, qué se le preguntaría a Jev y qué hay que medir antes de empezar. El plan
se escribe cuando le toca a cada uno, porque medir lo cambia: en el aprendizaje,
el dato contradijo al encargo cuatro veces.

## Qué es Jev

Un modelo que **decide, no que escribe**. Se le entrega una situación (una
conversación, un pago, una encuesta) y una o varias preguntas con sus opciones.
Devuelve la opción elegida y **qué tan seguro está**, de 0 a 1.

- No conversa ni redacta: para eso está el modelo de Luna.
- Cuesta unos US$0,00002 por decisión y responde en 0,1 a 0,2 segundos.
- Es de TypeSafe (`typesafe/jev-1.13`) y se llama por una ruta **en alfa** de
  OpenRouter, con la misma llave que ya usa Aremko. El nombre y la dirección
  pueden cambiar; por eso se cambian sin tocar código (ver abajo).

Tres tipos de pregunta:

- **`choice`:** una opción de una lista, con su confianza.
- **`noul`:** un sí o no, que llega como **la probabilidad de que sea sí**, de 0
  a 1. Esa probabilidad hace de confianza: 0,95 es un sí seguro, 0,05 un no
  seguro y 0,5 es no saber. Se decide «sí» por encima del umbral y «no» por
  debajo de su espejo (con 0,70: sí sobre 0,70, no bajo 0,30); lo del medio es
  dudoso.
- **`score`:** un punto de una escala, por ejemplo «puede esperar / hoy / ahora
  mismo». Todavía no se ha revisado si trae confianza.

## Cómo quedó instalado (25-09-2026)

- **El cliente.** `whatsapp_agent/decisiones.py`, función `decidir()`. Es el
  único lugar del código que habla con Jev. Si Jev no responde, tarda más de 2
  segundos, cambia de formato o falta la llave, devuelve «sin opinión» y todo
  sigue exactamente como antes. Lo mismo no se pregunta dos veces (caché de 12 h).
- **El registro.** Cada decisión queda en el admin, en *Decisiones del modelo*
  (`DecisionAgente`, solo lectura): para qué se usó, qué respondió, con qué
  confianza, cuánto costó y cuánto tardó.
- **El interruptor.** Cada uso tiene el suyo. El del aprendizaje está en
  *Configuración Agente WhatsApp → Aprendizaje (correcciones de Deborah)*. Hoy
  está apagado.
- **Cambiar de modelo o de ruta sin tocar código.** Variables de entorno en
  Render: `DECISIONES_RUTA`, `DECISIONES_MODELO` y `DECISIONES_ESPERA_SEG`.
  Vacías, usan los valores de hoy.
- **De dónde viene.** Portado de Datamatic (`apps/decisiones/decidir.py`), que
  lo usa en producción desde el 22-09-2026 para opinar sobre las conversaciones
  de su bandeja (su P-115). En Datamatic no se usa en nada más: Telar revisa
  con Claude Sonnet.

## Lo que cuesta de verdad

- **Aprendizaje de Luna:** unos US$0,00002 por corrección clasificada. Procesar
  todas las correcciones de un mes cuesta unos US$0,05.
- **Bandeja de Datamatic:** 24 conversaciones completas costaron US$0,00095 en
  total, con 192 ms de mediana.
- **Ninguno de los siete proyectos pasa de un dólar al mes.** El costo no es lo
  que decide; lo que decide es si acierta.

## Las reglas del juego

Aprendidas en el aprendizaje de Luna (25-09-2026) y en la bandeja de Datamatic
(21 y 22-09-2026). Valen para cualquier proyecto nuevo.

1. **Medir primero.** El dato gana, también contra el plan.
2. **Corrida en seco que Jorge lee** antes de prender nada: Jev decide, se
   imprime y no se guarda nada.
3. **Interruptor apagado de partida**, y si Jev falla todo sigue como antes.
4. **La confianza manda.** Bajo el umbral no decide (en el aprendizaje, 0,70) y
   lo dudoso va a una persona.
5. **La pregunta tiene que calzar con lo que pasa de verdad.** Preguntar «¿qué
   tipo de lección es?» dio 8 propuestas malas de 9. Preguntar «¿qué hizo
   Deborah?» (y sacar las plantillas) dio 3 de 3 reales.
6. **Mirar la conversación entera, no el mensaje suelto.** En Datamatic, un «Ok»
   suelto quedaba en 0,45 de confianza; con el hilo completo, entre 0,84 y 1,00.
7. **Sacar primero el ruido obvio con reglas fijas.** Las plantillas eran el 21%
   de las correcciones: no hacía falta preguntarle a Jev por ellas.
8. **No repetir.** Lo que ya está o ya se propuso no se vuelve a proponer.
9. **Nada que vea el cliente cambia sin el OK de Jorge:** ni el conocimiento de
   Luna, ni un precio, ni un mensaje.

## Cómo se arranca un proyecto

1. Jorge dice «vamos con el P-5x».
2. Se lee la ficha y se mide lo que dice *Qué medir antes de empezar*. Si el
   dato contradice la ficha, gana el dato.
3. Plan con el formato del encargo del aprendizaje (`PROMPT_JEV_AREMKO.md`, en
   el Escritorio de Jorge): contexto, datos, qué no hacer, etapas y reglas de
   la casa.
4. Con el «dale», por etapas: corrida en seco que Jorge lee, luego a producción
   con el interruptor apagado, y se prende con su OK.
5. Al cerrar, se actualizan la ficha, esta tabla y la línea de pendientes.

## Los proyectos

| P | Proyecto | Qué decidiría Jev | Cuándo | Estado |
|---|---|---|---|---|
| P-54 | Aprendizaje de Luna (en `PENDIENTES.md`) | ¿Qué hizo Deborah al corregir a Luna? ¿Enseña algo? | — | **En producción**, interruptor apagado. Falta la etapa 5 |
| P-55 | [Bandeja ordenada](P-55_bandeja_ordenada.md) | ¿En qué quedó la conversación? ¿Falta responder algo? | Primero | Listo para medir. Datamatic ya lo usa, como etiqueta |
| P-56 | [Pagos y transferencias](P-56_pagos_y_transferencias.md) | ¿A qué reserva corresponde este pago dudoso? | Primero | Espera una respuesta de Deborah (P-23) |
| P-57 | [Rescate de conversaciones](P-57_rescate_de_conversaciones.md) | ¿Vale la pena un seguimiento? ¿Cuál? | Después | Antes, re-medir el efecto de la carta (P-34a) |
| P-58 | [Encuestas y reseñas](P-58_encuestas_y_resenas.md) | ¿Es una queja? ¿De qué? ¿Urge? | Después | La regla ya existe y falta llenar un campo: el más chico |
| P-59 | [Tono de Luna](P-59_tono_de_luna.md) | ¿Suena natural o a robot? | Después | Espera la re-medición de P-53 |
| P-60 | [Telar: datos exactos](P-60_telar_datos_exactos.md) | ¿La pieza contradice los datos del negocio? | Después | Se construye en Datamatic |
| P-61 | [Control antes de enviar](P-61_control_antes_de_enviar.md) | ¿Es solo información? ¿Ofrece algo que no existe? | Al final | Solo cuando Luna pase a `auto_info` |

**Por qué este orden.** La bandeja y los pagos tocan venta y horas de trabajo,
y la bandeja ya está probada en Datamatic. El control antes de enviar es el más
valioso a largo plazo, pero va al final: primero la bandeja y el aprendizaje
tienen que mostrar cuánto se puede confiar en Jev con los datos de Aremko.

La receta que tienen en común: **una decisión que se toma muchas veces, entre
opciones conocidas, donde lo dudoso lo revisa una persona.** Un proyecto nuevo
que no calce con eso probablemente no es para Jev.
