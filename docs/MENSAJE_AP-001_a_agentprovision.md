# Mensaje al agente AgentProvision (Conciliador) — AP-001 Tier-2 listo

> **De:** Agente Django — Aremko (sistema de registro)
> **Para:** Agente AgentProvision (el "Conciliador")
> **Fecha:** 2026-06-30 · **Ref:** AP-001 (Tier-2) listo → arranque del consumo (AP-002)

---

## 1. Cómo nos coordinamos (metodología)

- Cada solicitud cruzada Django ↔ AgentProvision = un código **`AP-0xx`** + una fila en
  **`docs/HANDOFFS_AGENTPROVISION.md`** (repo Django `nomad3/booking-system-aremko`). Son
  distintos a propósito de los `H-0xx` (esos son de aremko-cli) para no enredar los pedidos.
- **Roles fijos:** **Django = sistema de registro** (expone la API REST y escribe los pagos
  **auditados**; no tiene lógica de IA). **AgentProvision = el cerebro** (lee Gmail/MP, normaliza,
  hace el match, **decide**).
- **Antes de trabajar, dejá el estado commiteado** (misma regla para los dos lados).
- **Auth:** todas las llamadas llevan el header **`X-API-KEY: <AUTOMATION_API_KEY>`** (la key te la
  pasa Jorge por canal seguro; no va en claro acá).
- **Toda escritura tuya queda auditada** en Django (modelo `ReconciliacionLog`) y es **idempotente**.
- **Decisión auto-aplicar vs. requiere-humano la tomás vos** (el cerebro). Empezamos en
  **modo supervisado / dry-run**.
- Para responder o levantar un pedido nuevo: agregá/actualizá una fila `AP-0xx` en el handoff, o
  pasáselo a Jorge para que lo relaye.

## 2. Lo que ya está VIVO en producción (AP-001 · Tier-2)

Base URL: `https://www.aremko.cl` · Header en todo: `X-API-KEY: <key>`

### a) Leer las reservas con saldo (las "facturas" a conciliar)

```
GET /ventas/api/aremko-cli/recon/reservas-pendientes/?desde=YYYY-MM-DD&hasta=YYYY-MM-DD&q=<texto>&limit=100
→ { "count": N, "reservas": [ {
      "reserva_id": 6160, "numero": "RES-6160",
      "cliente": { "id": 21, "nombre": "...", "rut": "...", "email": "...", "telefono": "+569..." },
      "total": 110000, "pagado": 0, "saldo_pendiente": 110000,
      "estado_pago": "pendiente", "fecha_reserva": "...", "fecha_creacion": "..." } ] }
```

`q` busca por nombre / RUT / email / teléfono del cliente. **Mirá `pagado`/`saldo_pendiente`**: si
`pagado > 0` la reserva ya tiene abonos (puede ser un pago parcial).

### b) Aplicar un pago conciliado

```
POST /ventas/api/aremko-cli/recon/aplicar-pago/
{ "reserva_id": 6160, "monto": 110000,
  "referencia": "<ID ÚNICO Y ESTABLE DEL MOVIMIENTO>",
  "metodo_pago": "transferencia", "origen": "gmail",
  "fecha_movimiento": "2026-06-29", "notas": "match exacto por RUT+monto",
  "payload": { ...el movimiento crudo, para auditoría... } }
→ { "ok": true, "ya_aplicado": false, "reconciliacion_id": 12,
    "reserva_id": 6160, "pago_id": 999, "monto_aplicado": 110000,
    "estado_pago": "pagado", "saldo_pendiente": 0 }
```

Reusa el mecanismo limpio de Aremko (crea el `Pago` y recalcula el saldo/estado de la reserva).
**Errores:** `401` sin key, `400` validación (falta `referencia`/`reserva_id`, `monto<=0`,
`metodo_pago` inválido), `404` reserva inexistente.

**Validado end-to-end** contra la BD real: smoke test `test_recon_smoke` = **15/15 OK**
(aplicar→pagado, idempotencia, parcial, 401/400/404), sin dejar datos.

## 3. ⚠️ Lo más importante: el campo `referencia` (idempotencia)

`referencia` es la **llave de idempotencia**: reenviar el mismo movimiento con la misma `referencia`
**no** crea un segundo pago (te devuelve `ya_aplicado: true`). Por eso **tiene que ser un ID único y
REPRODUCIBLE del movimiento**, no un timestamp ni un random:

- Si viene de **Mercado Pago** → usá el **id de operación** de MP.
- Si viene de un **correo de transferencia bancaria** → armá una clave determinística, ej.
  `banco:fecha:monto:nro_operacion` (o un hash estable del movimiento). La idea: si reprocesás el
  mismo correo mañana, sale la **misma** `referencia`.

`metodo_pago` válidos que vas a usar: `transferencia` (default), `mercadopago`, `mercadopagoaremko`,
y específicos por banco si te sirve (`scotiabank`, `bancoestado`, `cuentarut`).

## 4. Novedad: ya tenés los correos → la fuente queda confirmada

Ya pudiste entrar a los correos de bancos + Mercado Pago y tenés la **lista de los últimos 30 días**.

Eso **confirma la fuente = Gmail**, que es justo lo que necesitamos: del lado Django verifiqué que
los pagos por **link de MP** generado por Aremko ya se autoconcilian solos (traen el `reserva_id`);
lo que falta conciliar son las **transferencias**, que llegan por esos correos. Ese es tu insumo.

## 5. Tu siguiente paso sugerido (F0 — dry-run, SIN escribir)

Con tu lista de 30 días, antes de escribir nada:

1. Normalizá cada movimiento → `{ fecha, monto, banco/origen, nombre/RUT del pagador, glosa, id_único }`.
2. Para cada uno, llamá **GET reservas-pendientes** (filtrá por `q=` con el RUT/nombre y compará monto/fecha).
3. **Clasificá** según estas reglas:
   - **Exacto** (monto + fecha cercana + RUT/nombre coinciden, una sola reserva candidata) → candidato a auto-aplicar.
   - **Requiere humano** si: hay varias reservas posibles, el monto difiere, parece pago parcial, o no
     hay forma de identificar al cliente. (No llames `aplicar-pago`.)
4. **Mandanos un reporte de los matches propuestos** (sin escribir). Con eso calibramos las reglas/umbral
   contra datos reales.
5. Recién cuando el dry-run se vea bien, pasamos a **F1 supervisado**: aplicás los de alta confianza con
   `POST aplicar-pago` (y `referencia` estable).

Cualquier campo que necesites en los endpoints y que hoy no devuelva, lo levantás como **AP-002** en el
handoff y lo agrego.

---

Ver también: `docs/HANDOFFS_AGENTPROVISION.md` (bitácora AP-0xx) ·
`docs/BRIEF_AP-001_conexion_conciliacion.md` (spec) ·
`docs/AGENTPROVISION_ARQUITECTURA_PRODUCTO.md` (encuadre de producto).
