# H-037 — Luna Interna · Fase 0 (piloto con Jorge)

**Pedido por:** Jorge, 2026-06-22 · **Plan:** `docs/PLAN_LUNA_INTERNA.md`
**Reparto:** Django (cerebro/datos) + aremko-cli (canal/envío + routing de autonomía)

## Objetivo
Primer paso, 100% interno y de bajo riesgo: **Jorge** escribe "empezando el día" al WhatsApp de
Aremko → Luna lo reconoce por su número, lo saluda según el turno y le entrega su **briefing**
(pagos que vencen + saldos bajos + comandas/tareas pendientes). Valida toda la mecánica de
**identidad-por-número + respuesta automática a un número whitelisted**. De paso resuelve el pedido
del "resumen diario por WhatsApp".

> **Reactivo, no proactivo (clave):** la Fase 0 es Jorge ESCRIBE → Luna RESPONDE. Como él inicia,
> la ventana de 24h de WhatsApp está abierta y no necesitamos plantilla. El envío proactivo a las
> 11:00 queda para Fase 0.5 (necesita plantilla o depender de que él ya escribió).

## La base ya construida (Django, commit de esta sesión)
- App aislada `personal_operativo` con modelo **`PersonalOperativo`** = LA WHITELIST: `telefono`
  (E.164, único, la llave), `usuario` (FK User → de ahí se llega a `usuario.proveedor` para
  masajistas), `rol`, `turno`, **`responde_auto`** (interruptor de autonomía), `activo`.
- Admin **solo superusuarios**. Jorge se agrega ahí con su celular y `responde_auto=True`.

## Lo que falta — Django (mi lado, próximo)
1. **Detección de modo interno:** al procesar un mensaje, si el número está en `PersonalOperativo`
   (activo + responde_auto) → modo interno (no el flujo de ventas/cliente).
2. **Saludo + intent "empezando el día":** detectar "empezando el día / buenos días / inicio turno"
   → Luna saluda por nombre y turno ("Buenos días, Jorge" / "Buenas tardes…").
3. **Tool `mi_briefing`** (determinístico, en código): arma el briefing del que escribe:
   - Pagos que vencen ≤7 días + saldos bajo umbral (de `costos_web.ServicioWeb`).
   - Comandas/tareas pendientes del día (de `ventas.Comanda` / `control_gestion.Tarea` asignadas a
     su `usuario`).
   - (Agenda del día cuando esté el modelo a mano.)
4. **Señal de auto-envío:** la respuesta del agente para un número whitelisted viene marcada
   (ej. `responde_auto: true` / `auto_send: true`) para que aremko-cli la envíe sin el cajón.

## Lo que falta — aremko-cli (tu lado)
1. **Respetar el auto-envío:** cuando la respuesta de Luna venga marcada como `responde_auto`
   (número staff), **enviarla automáticamente** por WhatsApp, **sin pasar por el cajón de
   aprobación de Deborah**. (Para clientes, todo sigue igual: borrador → Deborah aprueba.)
   - A definir contigo: ¿prefieres que Django mande el flag en la respuesta, o que aremko-cli
     consulte un endpoint "¿este número es staff-auto?" (Django lo expone)? Propongo el flag en la
     respuesta (Django es el dueño de la whitelist) — dime qué te calza mejor.
2. **(Fase 0.5, después)** cron 11:00 que dispara el briefing proactivo (con plantilla o fallback).

## Flujo E2E (Fase 0)
Jorge escribe "empezando el día" → aremko-cli pide la respuesta a Django → Django ve número
whitelisted → Luna saluda + `mi_briefing` → respuesta marcada `responde_auto` → aremko-cli la envía
sola → Jorge recibe su briefing. Sin Deborah en el medio.

## Guardrails
- Autonomía SOLO para números en la whitelist (`responde_auto=True`); clientes sin cambios.
- Luna interna LEE y resume; en Fase 0 no cambia estados ni toca plata.
- Identidad/decisión de modo en código, no en el prompt (lección del modelo liviano).

## Para arrancar
Jorge: deploy + `migrate personal_operativo` + agregarse en el admin (su celular, rol=jefatura,
responde_auto=True). Luego Django construye `mi_briefing` y aremko-cli el auto-envío.
