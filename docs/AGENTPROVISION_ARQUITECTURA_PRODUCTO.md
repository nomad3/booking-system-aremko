# AgentProvision — Arquitectura de Producto

> Documento de estrategia/arquitectura para vender agentes IA a múltiples empresas, reusando el
> trabajo del cliente cero (Aremko). Casa final: repo `github.com/nomad3/agentprovision-agents`
> (hoy versionado junto al cluster AP-0xx en el repo Django). v1 — 2026-06-30.

---

## 0. Posicionamiento (qué vendemos)
**AgentProvision = plataforma multi-tenant de agentes de IA para la operación de una empresa.**
NO es "software de conciliación". La conciliación es **el primer caso de uso** (la cuña), entregado
por un **agente especializado** del catálogo. Naming:
- **Marca/servicio:** AgentProvision — *"agentes de IA para tu empresa"*.
- **Producto de entrada:** el agente **Conciliador**.
- **Caso de uso:** conciliación bancaria (vendible solo, ROI claro) — una función, no el techo.

Jugada: **plataforma con killer-app de entrada**. El Conciliador trae al cliente; la plataforma lo retiene y expande.

---

## 1. El modelo en 3 capas
```
┌──────────────────────────────────────────────────────────────┐
│ PLATAFORMA (multi-tenant): auth, RBAC, aislamiento, auditoría, │  ← ya existe (Alpha/Temporal)
│ orquestación de workflows, approval gates, observabilidad      │
├──────────────────────────────────────────────────────────────┤
│ CATÁLOGO DE AGENTES (templates reutilizables):                 │
│   Conciliador · [Cobrador · Facturador · Vigía · …]            │  ← se construye 1 vez c/u
├──────────────────────────────────────────────────────────────┤
│ CAPA DE CONECTORES (3 Tiers) — INFRA COMPARTIDA por todos      │  ← inversión horizontal
│   Fuentes (banco/mail/pago)  ·  Sistemas de registro (ERP)     │
└──────────────────────────────────────────────────────────────┘
```
Cada tenant (empresa) **activa los agentes que necesita** y los **conecta** a sus sistemas vía conectores.

---

## 2. Catálogo de agentes
**Un agente = template reutilizable, tenant-agnóstico, parametrizado por config (no por código).**
Convención de nombres "-ador":

| Agente | Qué hace | Estado |
|---|---|---|
| **Conciliador** | Lee movimientos (banco/pago), hace match contra facturas/reservas, registra el pago conciliado auditado | 🟢 en construcción (Aremko) |
| Cobrador | Detecta impagos y gestiona cobranza (avisos/seguimiento) | 🔭 roadmap |
| Facturador | Emite boletas/facturas (SII) desde ventas/reservas | 🔭 roadmap |
| Vigía | Alertas de flujo de caja / pagos próximos / anomalías | 🔭 roadmap |

**Principio de reuso:** el **motor del agente vive en AgentProvision** (extraer → normalizar → decidir → escribir), no en el cliente. Lo único por tenant = **config** (conectores, reglas, umbrales, etiquetas).

### El agente Conciliador (detalle)
- **Entrada:** movimientos normalizados desde un **conector de fuente** (fecha, monto, moneda, banco, cuenta, descripción, RUT/cliente, nº documento).
- **Proceso:** match contra el **sistema de registro** (vía conector ERP) → clasifica: exacto / probable / duplicado / parcial / sin match / requiere humano.
- **Salida:** escribe el pago conciliado vía el conector ERP (auditado), o lo deja en cola de revisión.
- **Config por tenant:** reglas de match (umbral de confianza, tolerancia de monto/fecha, qué identificadores usar), modo (dry-run / supervisado / auto), etiquetas.

---

## 3. Interfaz de conectores (3 Tiers) — infra de plataforma desde el día 1
Los conectores **NO son del Conciliador: son de AgentProvision**. El Cobrador y el Facturador usarán
el MISMO conector al ERP del cliente → se diseñan como infra compartida. Dos lados:

- **Conector de FUENTE** (entra dinero/datos): contrato = *"devuelve movimientos normalizados"*.
  Implementaciones: Gmail (aviso del banco), Mercado Pago (API/webhook), Transbank, Flow, Khipu,
  archivos de cartola (CSV/OFX/Excel), API del banco.
- **Conector de SISTEMA DE REGISTRO** (ERP/contable): contrato = los endpoints del **Adapter Spec**
  (`GET invoices/payments/customers`, `POST reconciliation-match`, `PATCH invoice`). Es lo que
  consume cualquier agente para leer/escribir en el sistema del cliente.

### Los 3 Tiers (de cómo se conecta el sistema de registro)
- **Tier 1 — Conectores pre-armados** (como los plugins de MP para Shopify): ERPs/contables comunes
  en Chile → **Bsale, Defontana, Nubox, Siigo, Softland**. Conectar y andar.
- **Tier 2 — Adapter Spec a medida:** clientes con sistema propio implementan los endpoints del
  contrato. **Aremko (Django) = la implementación de referencia #1.**
- **Tier 3 — Genérico (CSV/Excel/OFX):** la cola larga (PYMEs sin ERP) suben la cartola; el agente
  trabaja sobre eso. Cero integración → venta self-service.

> **Los 3 Tiers se consideran desde el inicio:** se define la INTERFAZ del conector ahora (aunque
> Aremko solo ejercite Tier 2 + fuente MP/Gmail), de modo que los tres "enchufen" igual después.

---

## 4. Modelo de tenant (multi-tenant nativo — ya existe)
- **Tenant = empresa.** Tiene SUS agentes activados, SUS conectores, SU config y **aislamiento de datos**.
- **Aremko = tenant cero:** agente Conciliador activado + conector Tier 2 (su Django) + fuente (MP/Gmail).
- **Vender = dar de alta un tenant + activar los agentes** que necesita. El Conciliador es el SKU de entrada.
- **Onboarding repetible (playbook):** conectar fuente → conectar sistema de registro (Tier 1/2/3) →
  configurar reglas → demo en **dry-run** → go-live supervisado → auto.

---

## 5. Modelo comercial / pricing
- **Suscripción de plataforma** (fee por tenant) **+ agentes como SKU/add-on** (Conciliador, Cobrador…)
  **+ setup de conector** (one-time, según Tier).
- **Conciliador vendible solo** (entrada barata, ROI claro) → después se sube al cliente al resto del
  catálogo sobre la **misma conexión** = **land & expand**.
- **Tier 3 (CSV) = plan self-service** barato para la cola larga; Tier 1/2 = cuentas más grandes con onboarding.
- Escalado por **volumen de movimientos/transacciones** del tenant.
- Propuesta de valor (3 números a mostrar): **horas/mes ahorradas**, **% auto-conciliado**, **0 fraude**
  (lee de la fuente confiable, no del cliente).

---

## 6. Cómo NO construir one-offs (regla de oro)
1. **El motor del agente vive en AgentProvision**, tenant-agnóstico. El cliente solo aporta el conector.
2. **Reglas y umbrales = config por tenant**, no código.
3. **El Adapter Spec es EL contrato** (Tier 2). La API `recon` de Aremko/Django = referencia #1 + documento vendible.
4. **Todo conector implementa la misma interfaz** → sumar clientes = configurar, no reprogramar.
5. **Auditoría + RBAC + approval gates por tenant** desde el inicio.

---

## 7. Roadmap
- **F1 — Conciliador + tenant cero (Aremko):** construir el agente como template + el conector Tier 2
  (Django `recon`, ver `BRIEF_AP-001`) + publicar el **Adapter Spec**. Demo de onboarding en dry-run.
- **F2 — 2º tenant + primer Tier 1:** elegir el ERP más común del pipeline y construir ese conector pre-armado.
- **F3 — Expandir catálogo:** Cobrador / Facturador / Vigía sobre los tenants ya conectados (costo marginal bajo).
- **Transversal:** one-pager comercial + demo reusable + catálogo de conectores priorizado para Chile.

---

## 8. Cómo se conecta con lo que ya hay
- **Coordinación Django↔AgentProvision:** handoffs `AP-0xx` en `docs/HANDOFFS_AGENTPROVISION.md`.
- **AP-001:** la conexión de conciliación de Aremko = la primera implementación del Adapter Spec (Tier 2).
- **Código de AgentProvision:** `github.com/nomad3/agentprovision-agents`.
- Ver memorias del proyecto: consultora/AgentProvision + conciliación de pagos Aremko.
