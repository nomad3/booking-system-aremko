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
| AP-001 | **Conexión API para conciliación bancaria (onboarding Aremko).** Conectar AgentProvision a la API de Django para que lea clientes/reservas/pagos y escriba los pagos conciliados. Reusar lectura existente; construir un módulo chico de escritura (recon) bajo `AUTOMATION_API_KEY` que reusa `VentaReserva.registrar_pago` + auditoría. Fuente de los movimientos: Gmail (aviso del banco/MP) y/o el webhook MP que ya existe. Detalle, mapeo de endpoints y decisiones pendientes en `docs/BRIEF_AP-001_conexion_conciliacion.md`. | Django (API recon) + AgentProvision (conector + workflow) | 🔵 INTEGRADO — **lado Django COMPLETO y validado; falta que AgentProvision lo consuma end-to-end (próximo handoff).** **PASO 1 (lectura) vivo:** `GET /ventas/api/aremko-cli/recon/reservas-pendientes/` (read-only). **PASO 2 (escritura, LEAN) vivo + migrado:** `POST /ventas/api/aremko-cli/recon/aplicar-pago/` — reusa el mecanismo limpio (crea `Pago` + recalcula saldo), idempotente por `referencia`, auditado en app aislada `conciliacion.ReconciliacionLog`. Migración `conciliacion.0001_initial` **aplicada en Render**. **Validado: smoke test `python manage.py test_recon_smoke` = 15/15 OK** (aplicar/idempotencia/parcial/401/400/404; no-destructivo con rollback + sin envíos). Código: `ventas/views/recon_api_views.py` + `conciliacion/`. NB: `conciliacion/tests.py` (unittest) no corre por el drift AR-034 (no se puede construir test_db); por eso el smoke command. Decisiones: 1=LEAN, 2=Gmail, 3=F0. | 2026-06-30 (agente Django) |
| AP-002 | **AgentProvision consume los endpoints + conciliación F0 (dry-run).** El agente AP arma el workflow que lee los correos de abonos (Gmail `abonosaremko@gmail.com`, alias `ventas@aremko.cl`), normaliza los movimientos y los matchea contra `GET recon/reservas-pendientes`; en F0 **NO escribe** (`aplicar-pago` deshabilitado). Reglas de `referencia` estable para idempotencia. | AgentProvision (workflow `aremko-bank-reconciliation` v0.2.0, repo `agentprovision-agents`, commit `d2e06b2`) + Django (endpoints ya vivos) | 🟧 EN PROGRESO — workflow F0 construido y commiteado del lado AP; **bloqueado por `AUTOMATION_API_KEY`** (Jorge debe entregársela al agente AP por canal seguro). Sin escrituras ni cambios de labels en Gmail. **Próximo:** correr F0 real → reporte de matches propuestos para calibrar reglas antes de F1. | 2026-06-30 (agente Django, registrando el reporte del agente AP) |

## Estados
🟡 DISEÑO · 🟧 EN PROGRESO · 🔵 INTEGRADO (falta validación de Jorge) · ✅ CERRADO

## Reglas del protocolo (para ambos lados)
- Cada solicitud cruzada = un **ID `AP-0xx`** + una fila en esta tabla + (si es grande) un `docs/BRIEF_AP-0xx_*.md`.
- **Fuente única de coordinación = ESTE archivo** (repo Django `nomad3/booking-system-aremko`). El agente AP tiene **acceso de lectura** a este repo y lo lee acá; el agente Django **no** tiene acceso al repo de AgentProvision. Si AP mantiene una copia del handoff en su repo, es **espejo, no fuente** (evitar divergencia). Como AP no puede escribir acá, el **agente Django registra las filas `AP-0xx` en nombre de AP** a partir de su reporte.
- **Estado commiteado ANTES de trabajar** (mismo criterio que los `H-0xx`).
- **Auth:** AgentProvision usa `AUTOMATION_API_KEY` (header `X-API-KEY`), la key de automatizaciones.
- **Toda escritura desde AgentProvision queda AUDITADA en Django** (MovimientoCliente y/o log de conciliación) y es reversible.
- **Umbral de confianza:** Django aplica el pago tal cual lo manda AgentProvision; la decisión "auto-aplicar vs. requiere humano" la toma AgentProvision (el cerebro). Empezamos en modo supervisado.
- Ver también `docs/HANDOFFS.md` (H-0xx, aremko-cli) y la memoria del proyecto de conciliación + AgentProvision.
