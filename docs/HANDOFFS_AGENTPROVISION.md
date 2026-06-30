# HANDOFFS — AgentProvision ↔ Django (Aremko)

> Bitácora de encargos cruzados entre el **agente Django** (`~/dev/booking-system-aremko`, el
> SISTEMA DE REGISTRO de Aremko) y **AgentProvision** (el agente operativo EXTERNO; producto de
> Jorge + Simón, Aremko = cliente cero). Si se corta la sesión/energía, este archivo + `git log`
> reconstruyen en qué quedamos.
>
> **Códigos `AP-0xx`** — distintos a propósito de los `H-0xx` de aremko-cli (`docs/HANDOFFS.md`),
> para NO enredar las solicitudes cuando lleguen de los dos lados.
>
> **Rol de cada lado:**
> - **AgentProvision = el cerebro.** Lee Gmail / Mercado Pago, extrae y normaliza movimientos,
>   hace el match contra Django, decide y clasifica (exacto / probable / sin match / requiere humano).
> - **Django = el sistema de registro.** Expone la API REST (lectura) y recibe las escrituras
>   conciliadas (pagos), siempre AUDITADAS. No tiene lógica de IA; es la fuente de verdad.

## Tabla de handoffs

| ID | Qué | Implementa | Estado | Última actualización |
|----|-----|-----------|--------|----------------------|
| AP-001 | **Conexión API para conciliación bancaria (onboarding Aremko).** Conectar AgentProvision a la API de Django para que lea clientes/reservas/pagos y escriba los pagos conciliados. Reusar lectura existente; construir un módulo chico de escritura (recon) bajo `AUTOMATION_API_KEY` que reusa `VentaReserva.registrar_pago` + auditoría. Fuente de los movimientos: Gmail (aviso del banco/MP) y/o el webhook MP que ya existe. Detalle, mapeo de endpoints y decisiones pendientes en `docs/BRIEF_AP-001_conexion_conciliacion.md`. | Django (API recon) + AgentProvision (conector + workflow) | 🟡 DISEÑO — spec y mapeo listos; pendientes 3 decisiones de Jorge (ver brief). Aún NO se construyó nada. | 2026-06-30 (agente Django) |

## Estados
🟡 DISEÑO · 🟧 EN PROGRESO · 🔵 INTEGRADO (falta validación de Jorge) · ✅ CERRADO

## Reglas del protocolo (para ambos lados)
- Cada solicitud cruzada = un **ID `AP-0xx`** + una fila en esta tabla + (si es grande) un `docs/BRIEF_AP-0xx_*.md`.
- **Estado commiteado ANTES de trabajar** (mismo criterio que los `H-0xx`).
- **Auth:** AgentProvision usa `AUTOMATION_API_KEY` (header `X-API-KEY`), la key de automatizaciones.
- **Toda escritura desde AgentProvision queda AUDITADA en Django** (MovimientoCliente y/o log de conciliación) y es reversible.
- **Umbral de confianza:** Django aplica el pago tal cual lo manda AgentProvision; la decisión "auto-aplicar vs. requiere humano" la toma AgentProvision (el cerebro). Empezamos en modo supervisado.
- Ver también `docs/HANDOFFS.md` (H-0xx, aremko-cli) y la memoria del proyecto de conciliación + AgentProvision.
