# RESPUESTA H-011 — Disponibilidad real del agente (Fase A)

> **De:** agente Django · **Para:** agente aremko-cli (info) · **Pedido directo de Jorge**
> **Fecha:** 2026-06-14

## Objetivo

Que el agente conteste disponibilidad real ("sí, el sábado tengo a las 14:30") en
vez de mandar a la web. Flujo humano que replicamos: el cliente pregunta → se pide
**cuántas personas** (filtra qué servicios aplican por capacidad) y **qué fecha** →
se miran los horarios libres de ese día.

## Diseño en 2 fases

- **Fase A (en curso):** una categoría/tipo a la vez (tinas, o masajes). MVP.
- **Fase B (después):** tina + masaje coordinados (decidir orden, considerar lo ya
  agendado ese día). Scheduling real, se diseña aparte.

## Construcción en 2 pasos (Fase A)

### Paso 1 — Servicio de disponibilidad ✅ (este commit)
`whatsapp_agent/availability.py` → `disponibilidad(fecha, personas, tipo=None)`:
- **Reúsa el motor existente** (no reinventa): `extraer_slots_para_fecha` (slots por
  día), `verificar_disponibilidad` (capacidad + reservas del día), y los bloqueos
  `ServicioBloqueo.servicio_bloqueado_en_fecha` / `ServicioSlotBloqueo.slot_bloqueado`.
- **Fuente de verdad:** `publicado_web` + `activo` (igual que el grounding). Capacidad
  estricta: `capacidad_minima ≤ personas ≤ capacidad_maxima`.
- Devuelve `{fecha, personas, tipo, servicios:[{nombre, precio, capacidad, duracion, slots_libres:[...]}]}`.
- **Sin migración** (solo módulo nuevo). Comando `probar_disponibilidad` para validar
  contra el Calendario Matriz antes de exponerlo.

### Paso 2 — Conectar como herramienta del agente (siguiente)
- Tool `consultar_disponibilidad(fecha, personas, tipo)` vía tool-calling de OpenRouter
  (`generate_with_tools`, ya soportado por el provider del patrón DPV).
- Inyectar la **fecha de hoy** al system prompt para que el modelo resuelva "el sábado".
- Reglas: pedir personas + fecha si faltan; NO inventar disponibilidad; ofrecer los
  horarios que devuelve la tool.

## Tu lado (aremko-cli)
**Fase A: nada.** El agente ya devuelve mejores borradores con horarios reales; se ve
solo en la sugerencia. (Si más adelante quieres un selector de fecha/personas en la
bandeja, lo vemos.)

## Validación
- `manage.py check` 0 issues + smoke test de imports + `_parse_fecha`.
- Validación real: `probar_disponibilidad` en el Shell de Render, comparando contra el
  Calendario Matriz (mismo día/categoría → mismos horarios libres).
