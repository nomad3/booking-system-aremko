# BRIEF AP-001 — Conexión API para conciliación bancaria (AgentProvision ↔ Django)

> **De:** agente Django (`~/dev/booking-system-aremko`)
> **Para:** AgentProvision (agente operativo externo) + Jorge
> **Estado:** 🟡 DISEÑO. Mapeo y spec listos; faltan 3 decisiones de Jorge (§8). Aún NO se construyó nada.

---

## 1. Objetivo y arquitectura

Conectar **AgentProvision** (el cerebro) con **Django** (el sistema de registro) para automatizar la
**conciliación bancaria** de Aremko (primer caso de uso del agente operativo).

```
Gmail / Mercado Pago ──► AgentProvision (lee, extrae, normaliza, hace match, decide)
                                   │  (API REST, AUTOMATION_API_KEY)
                                   ▼
                              Django (lee reservas/pagos/clientes; recibe el pago conciliado, auditado)
```

AgentProvision tiene los movimientos bancarios; Django expone los datos para el match y recibe la
escritura. Django NO tiene lógica de IA — es la fuente de verdad.

## 2. Base URL y ambientes
- **Prod:** `https://aremko.cl` (fallback Render: `aremko-booking-system-prod.onrender.com`).
- **NO hay staging/sandbox separado** (solo prod en Render). ⚠️ Por eso AgentProvision debe operar
  en **modo "dry-run"** durante el onboarding (proponer matches SIN escribir) hasta validar.

## 3. Autenticación
AgentProvision usa **`AUTOMATION_API_KEY`** → header **`X-API-KEY: <valor>`** (la key de
automatizaciones, ya usada por aremko-cli y los cron). Se obtiene del panel de Render (env var
`AUTOMATION_API_KEY`). (Existen otras 2 keys —`LUNA_API_KEY` y Token DRF— pero para el agente
externo usamos la de automatización.)

## 4. Endpoints que YA EXISTEN (reutilizar)

| Necesidad (plan) | Endpoint Django | Método | Auth | Nota |
|---|---|---|---|---|
| GET customers | `/api/luna/cliente/?q=` (busca por email/teléfono/nombre/RUT) | GET | LUNA_API_KEY | resolver cliente por RUT/nombre |
| GET customer ficha | `/ventas/api/aremko-cli/clientes/{id}/ficha/` | GET | AUTOMATION | historial del cliente |
| GET invoices (=reservas) | `/ventas/api/aremko-cli/bookings/detalle/` | GET | AUTOMATION | detalle línea a línea |
| GET reservas (DRF) | `/ventas/api/ventasreservas/` | GET | Token | total/saldo/estado_pago (paginado 20) |
| GET payments | `/ventas/api/pagos/` | GET | Token | monto/método/fecha (paginado 20) |

> ⚠️ Los ViewSets DRF (`/ventas/api/...`) usan **Token** (login de usuario), no `AUTOMATION_API_KEY`.
> Para no mezclar auth, el módulo recon (§5) expone las lecturas que el agente necesita bajo
> `AUTOMATION_API_KEY`.

## 5. Endpoints a CONSTRUIR — módulo "recon" (bajo `AUTOMATION_API_KEY`)

1. **`GET /api/aremko-cli/recon/reservas-pendientes/`** → reservas con `estado_pago` en
   (`pendiente`, `parcial`), con `{id, cliente{nombre, rut, email, telefono}, total, pagado,
   saldo_pendiente, fecha_reserva, fecha_creacion}`. Filtros: `?desde=&hasta=&q=`. Son las "invoices a
   conciliar".
2. **`POST /api/aremko-cli/recon/aplicar-pago/`** (= `/reconciliation-matches` del plan) →
   body `{reserva_id, monto, metodo_pago='transferencia', referencia, fecha_movimiento, confianza,
   fuente}` → reusa **`VentaReserva.registrar_pago(monto, metodo_pago)`** (recalcula
   `pagado`/`saldo`/`estado_pago` solo) + **auditoría** (MovimientoCliente con la referencia/fuente).
   Devuelve `{ok, reserva_id, estado_pago, saldo_pendiente}`. **Idempotente** por `referencia` (no
   aplicar dos veces el mismo movimiento).
3. *(Opcional, según decisión §8)* `POST /api/aremko-cli/recon/movimiento/` + modelos
   `MovimientoBancario` y `ReconciliacionLog` → si querés que Django también guarde los movimientos
   crudos (`/bank-transactions` del plan) y el log de matches. Si vamos "lean", esto NO se construye
   (AgentProvision guarda los movimientos).

## 6. Modelo de datos (para el normalizador de AgentProvision)
- **`Cliente`** (ventas/models.py:759): `nombre`, `email`, `telefono` (+56…, único), `documento_identidad` (RUT), `region`, `comuna`.
- **`VentaReserva`** (ventas/models.py:1133) = la "invoice": `id`, `cliente` (FK), `total`, `pagado`, `saldo_pendiente`, `estado_pago` (pendiente|pagado|parcial|cancelado), `fecha_reserva`, `fecha_creacion`. Método clave: `registrar_pago(monto, metodo_pago)`.
- **`Pago`** (ventas/models.py:1300): `venta_reserva` (FK), `monto` (CLP), `fecha_pago` (clave para el match), `metodo_pago` (choices: transferencia, mercadopago, flow, webpay, efectivo, giftcard… + bancos chilenos).
- **NO existen** modelos de banco/cuenta/movimiento (se crearían solo si se elige la opción "completo").

## 7. 🔑 Hallazgo: Mercado Pago ya tiene endpoints (VERIFICADO 2026-06-30)
El repo YA tiene una integración **Mercado Pago "Link" real** (no stub):
`ventas/views/mercadopago_views.py` + `ventas/services/mercadopago_service.py`.
- **`create_mercadopago_payment`** crea una *preference* de Checkout Pro (`/checkout/preferences`)
  con `external_reference = reserva_id` y `notification_url` al webhook. O sea: Aremko **genera un
  link de pago para una reserva concreta** y el cliente paga ahí.
- **`mercadopago_webhook`** recibe la notificación, consulta el pago en MP y, si está `approved`,
  registra el `Pago` con `metodo_pago='mercadopago_link'`.
- **Implicancia para la conciliación:** lo que pasa por este flujo (pago vía link generado por Aremko)
  **se concilia solo** porque trae el `reserva_id` en `external_reference`. Lo que el **Conciliador**
  debe resolver es el resto: **transferencias** que el cliente hace a la cuenta de Aremko (banco o MP
  Cuenta Vista), que llegan **sin `reserva_id`** y hoy Deborah matchea a mano. Esas NO disparan este
  webhook → su rastro es el **correo de aviso** ("Recibiste $X de [nombre]"). **→ Fuente = Gmail.**
- ⚠️ **Bug detectado (aparte, flagueado):** el webhook hace `Pago.objects.create()` directo y **no
  recalcula el saldo** (los signals de `Pago` retornan temprano si no es giftcard) → la reserva queda
  `pendiente` aunque el pago MP haya llegado. Debe usar `reserva.registrar_pago(...)`. Arreglar antes
  de activar MP Link en prod. (No bloquea AP-001.)

## 8. Decisiones (estado 2026-06-30)
1. **¿Dónde viven los movimientos bancarios?** (A) Lean: AgentProvision los tiene, Django solo recibe el pago aplicado + auditoría (recomendado para MVP). (B) Completo: Django guarda `MovimientoBancario` + `ReconciliacionLog`. → **PENDIENTE (única que falta para construir PASO 2).**
2. ~~**¿Fuente de los movimientos?**~~ **RESUELTO (§7):** **Gmail** (aviso de transferencia). El webhook MP solo cubre pagos por link generado por Aremko, que ya se autoconcilian.
3. ~~**¿Arranque?**~~ **RESUELTO:** se hizo F0 primero. **PASO 1 (lectura) ya está VIVO en prod:** `GET /ventas/api/aremko-cli/recon/reservas-pendientes/` (commit `d4866ce`).

## 9. Plan por fases
- **F0 — Conectar (dry-run):** AgentProvision recibe la `AUTOMATION_API_KEY` + usa las lecturas (clientes/reservas). Lee movimientos (Gmail/MP), **propone matches SIN escribir**. Cubre la "Demo de onboarding" del plan.
- **F1 — Escribir (supervisado):** Django construye `recon/reservas-pendientes/` + `recon/aplicar-pago/` (reusa `registrar_pago` + auditoría + idempotencia). AgentProvision aplica matches de alta confianza.
- **F2 — Auditoría/triggers:** opción (B) si se elige + activar triggers automáticos + reporte de excepciones.

## 10. Reglas de negocio MVP (del plan de Jorge, mapeadas)
- **Match exacto:** monto + fecha cercana + referencia/RUT coinciden → AgentProvision puede auto-aplicar (F1).
- **NO auto-aplicar** si: múltiples reservas posibles, el monto difiere, parece pago parcial, o falta identificador de cliente → `requiere_humano` (queda para revisión, no se llama `aplicar-pago`).
- **Todo cambio auditado** en Django (lo garantiza `aplicar-pago`).
