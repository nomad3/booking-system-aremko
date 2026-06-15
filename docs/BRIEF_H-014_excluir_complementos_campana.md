# BRIEF H-014 — Excluir servicios complementarios al segmentar/redactar la campaña de la Bandeja

**Pedido por:** Jorge (vía agente aremko-cli) · 2026-06-15
**Lado que implementa:** Django (la campaña vive aquí; aremko-cli solo muestra/envía)

## Síntoma (visto en prod 2026-06-15)
En la campaña de la Bandeja WhatsApp (H-012), algunos clientes reciben un mensaje
que **menciona / se segmenta por un servicio COMPLEMENTARIO** en vez del servicio
**PRINCIPAL** que realmente contrataron. Ejemplos vistos por Jorge: mensajes cuyo
servicio mencionado era **"Tina Hidromasaje Niño"** y **"Tina Normal Niño"**.

El caso real: el cliente contrató una tina principal (ej. **Tina Hidromasaje Llaima**)
y le **agregó 1–2 "niños"** como complemento a esa tina. El mensaje debe referirse al
**servicio principal**, nunca al complemento.

Jorge también pide excluir **"Tina de Agua Fría Yates"** (complemento $0).

## Lo que ya existe (reusar, NO crear de nuevo)
H-011 ya creó `WhatsAppAgentConfig.servicios_complementarios` (M2M, en `whatsapp_agent`,
no toca `Servicio`) y el comando `marcar_complementos` que pre-llenó **7 complementos**:
4 decoraciones + Tina de Agua Fría Yates ($0) + 2 tinas niño. El **grounding** y la
**disponibilidad** del agente YA excluyen esa lista. La campaña **NO** la usa todavía.

## Pedido concreto
1. Que la lógica de **segmentación / elección de script** y el **contexto de render**
   de `ventas/management/commands/generar_bandeja_whatsapp_diaria.py` (y la taxonomía
   que clasifica al cliente: estado/estilo/eje_valor/etc.) **determinen el servicio
   PRINCIPAL del cliente EXCLUYENDO** los `WhatsAppAgentConfig.servicios_complementarios`.
   - Si un cliente tiene tina principal + complementos → el principal manda (clasificación
     y cualquier nombre de servicio que aparezca en el texto).
   - Si tras excluir complementos el cliente **no** tiene un servicio principal calificable
     → no generar envío (tratar como "sin script", como ya se hace).
2. **No usar plantillas/scripts cuyo contenido se base en un complemento.** Si una
   `ScriptWhatsApp` quedó asociada a un servicio complementario, no debe seleccionarse.
3. Confirmar que los 3 que nombró Jorge (**Tina Hidromasaje Niño**, **Tina Normal Niño**,
   **Tina de Agua Fría Yates**) estén efectivamente en `servicios_complementarios`
   (deberían, por `marcar_complementos`); si falta alguno, agregarlo.

## Resultado esperado
Los mensajes de la campaña solo mencionan/segmentan por **servicios principales**. Los
envíos "En Prueba" que hoy están basados en un complemento deberían dejar de generarse
(o regenerarse apuntando al principal) en la próxima corrida.

## aremko-cli
Nada — solo muestra la lista "Envíos por aprobar" y envía. Queda a la espera de validar
en prod con Jorge.

## Notas de drift (AR-034)
Reusar la M2M existente de `whatsapp_agent`; idealmente **sin migración nueva**. Si hay
que tocar algo de `ventas`, seguir el patrón drift-safe ya usado en H-011 (cuidado con
`makemigrations` volcando el drift de `ventas`).
