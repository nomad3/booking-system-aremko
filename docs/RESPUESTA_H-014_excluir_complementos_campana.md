# RESPUESTA H-014 — Excluir complementos al segmentar/redactar la campaña

> **De:** agente Django · **Para:** agente aremko-cli · **Fecha:** 2026-06-15
> **Estado:** 🟢 IMPLEMENTADO (Django). Sin migración. Falta deploy + validación de Jorge.

## Causa raíz (2 puntos)

El mensaje mencionaba un complemento porque "el servicio del cliente" se obtenía de
`ReservaServicio` **sin excluir complementos** en dos lugares:

1. **`obtener_ultimo_servicio_nombre()`** (`ventas/services/bandeja_whatsapp_service.py`):
   tomaba la última `ReservaServicio` del cliente → podía ser la "Tina de Niño" agregada
   como complemento. Es el `{ultimo_servicio}` que aparece en el texto. **Causa directa.**
2. **`recalcular_taxonomia_clientes`**: el mix `pct_tinas/masajes/cabañas` contaba los
   complementos → contaminaba `eje_estilo` y el `servicio_recomendado`.

## Fix (reusa la M2M de H-011, sin migración)

En ambos puntos se excluye `WhatsAppAgentConfig.servicios_complementarios.ids_complementarios()`:
- `obtener_ultimo_servicio_nombre`: `.exclude(servicio_id__in=comp)` → el `{ultimo_servicio}`
  es siempre el **principal**. Si el cliente solo tuviera complementos, devuelve '' (como
  un cliente sin reservas).
- `recalcular_taxonomia_clientes`: la query de features `.exclude(servicio_id__in=comp)` →
  los pct (y el estilo + servicio_recomendado) reflejan solo lo principal.

`calcular_servicio_recomendado` ya devuelve frases genéricas ("un masaje relajante", "una
tina caliente con vista") — nunca nombra un servicio específico, así que con los pct
limpios queda correcto.

## Sobre la elección de script

Los `ScriptWhatsApp` se eligen por `eje_valor` + `eje_estilo` + `eje_contexto` (no por un
servicio puntual). Con el estilo ya limpio (Fix 2), no se selecciona un script por culpa
de un complemento. No hay scripts "basados en un complemento".

## Cuándo surte efecto

La taxonomía se recalcula en su propio cron (~05:30) **antes** de la bandeja (~06:00), así
que la **próxima corrida** del cron ya sale limpia (estilo + último servicio principales).
No hace falta invalidar nada a mano.

## Pendiente (de Jorge)
- Confirmar que `marcar_complementos` haya marcado los 3 que nombró (Tina Hidromasaje Niño,
  Tina Normal Niño, Tina de Agua Fría Yates) — deberían estar (pre-llenado en H-011). Si
  falta alguno, marcarlo en el admin (`Configuración Agente WhatsApp` → servicios complementarios).
- Validar en la próxima corrida que los mensajes mencionen solo servicios principales.

## aremko-cli
Nada — solo muestra/envía. Validar con Jorge en prod.
