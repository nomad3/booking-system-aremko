# BRIEF H-028 — Luna crea reservas (v1: solo TINAS, con aprobación de Deborah)

**Pedido de Jorge (2026-06-18). El salto a "pantalones largos":** que Luna, cuando
tenga toda la información, **genere una reserva en el sistema**. Hasta ahora Luna
solo sugiere/responde; aquí ejecuta una ACCIÓN que ESCRIBE en el sistema de reservas.

Diseñado con el agente aremko-cli + Jorge.
**Alcance v1: SOLO TINAS** (1 día, lo más frecuente; menor riesgo para estrenar la creación).
Alojamiento/masaje/packs = fases siguientes.

## Decisiones de Jorge (cerradas)
1. **Disparo de la creación = Deborah aprueba con un botón.** Tras el "sí" del cliente,
   en la bandeja aparece un botón "Crear reserva"; Deborah da el OK final. Humano en el loop.
2. **Identificación del cliente por teléfono:**
   - WhatsApp: el teléfono ya está → no se pide. Instagram/Messenger: Luna lo pide.
   - `verificar_cliente(telefono)`: si el cliente EXISTE → no pedir datos personales, SALVO
     que le falte **mail o ciudad** → pedir solo lo que falte y completar su ficha.
   - Cliente NUEVO (nunca reservó) → pedir **nombre completo, mail, ciudad de residencia, RUT**.
3. **Resumen + confirmación ANTES de crear:** Luna muestra nombre + celular, servicios con
   fecha y hora, cantidad y valor → solo con el "sí" del cliente se habilita la creación.
4. **Pago vía el resumen existente:** DESPUÉS de crear la reserva, Django ya tiene **un botón
   en la reserva que genera un resumen con los datos de pago**. Luna debe **traer ese resumen**
   y entregarlo al cliente en la conversación para que pague.

## Flujo end-to-end (v1 tinas)
1. Cliente elige tina + fecha/hora/personas (reusa el flujo de disponibilidad H-011).
2. Identificación: WhatsApp (teléfono conocido) / IG-Messenger (Luna pide teléfono) →
   `verificar_cliente` → recolectar datos faltantes según el caso (conversacional, en modo borrador).
3. Luna arma el **resumen** y pide confirmación al cliente.
4. Cliente confirma → en la bandeja aparece **"Crear reserva"** → Deborah aprueba.
5. Django **crea la reserva** (re-verifica disponibilidad, idempotente).
6. Django **genera el resumen de pago** (botón existente) → aremko-cli lo postea en la
   conversación (Luna se lo envía al cliente).

## Arquitectura propuesta (a confirmar/ajustar por django)
Para que el botón "Crear reserva" sepa QUÉ crear sin parsear texto libre de Luna:
- Cuando Luna arma el resumen, llama un tool **`preparar_reserva(...)`** que **valida**,
  **re-verifica disponibilidad** y **guarda una "propuesta de reserva" estructurada** ligada
  a la conversación (estado `propuesta`/pendiente-de-aprobación), y devuelve el texto del resumen.
  Datos: `{ canal, external_id/telefono, datos_cliente (si faltan), servicio_id (tina), fecha,
  hora, personas, valor }`.
- La bandeja muestra el botón "Crear reserva" cuando hay una `propuesta` para esa conversación
  (Django lo expone, p.ej. en el read de la conversación, como hoy expone `sugerencia_agente`).
- **`crear_reserva(propuesta_id)`** (lo dispara el botón de Deborah → endpoint Django):
  - RE-VERIFICA disponibilidad (entre el resumen y la aprobación pudieron pasar horas) → si ya
    no hay cupo, responde error claro (no crea) para que Luna avise.
  - **Idempotente**: si la propuesta ya se creó, devolver la reserva existente (no duplicar).
  - Crea `VentaReserva` + `ReservaServicio` reusando EXACTAMENTE el camino de creación de la web
    (no tocar esos modelos a ciegas — ⚠️ **riesgo AR-034**, drift de modelos de ventas).
  - Devuelve `{ reserva_id, resumen_pago }` (el texto del botón de resumen existente) — o exponer
    `GET /api/reserva/<id>/resumen` para que aremko-cli lo traiga.

## Preguntas para Django (de su modelo/código)
1. **¿Cómo se crea hoy una reserva de tina** (qué función/endpoint usa el flujo web)? Para reusarlo.
2. **El "botón que genera el resumen con datos de pago"**: ¿qué genera exactamente y cómo
   exponerlo como endpoint/string para que Luna lo traiga? (¿incluye monto de abono + instrucciones/link de pago?)
3. ¿Conviene guardar la `propuesta` en una tabla nueva (app aislada, drift-safe) o hay un estado
   de pre-reserva ya disponible? (Si tabla nueva → migración manual en Shell de Render.)
4. ¿`verificar_cliente` necesita endpoint nuevo o ya existe lookup por teléfono? (existe
   normalización de teléfono +56 en el sistema.)
5. RUT: ¿formato/validación requerida al crear cliente nuevo? ¿obligatorio?

## aremko-cli (yo) — lo construyo cuando el contrato esté claro
- Botón "Crear reserva" en la bandeja (aparece cuando hay `propuesta`) → llama `crear_reserva`.
- Traer el `resumen_pago` y postearlo en la conversación como mensaje de Luna.
- La recolección de datos + el resumen son borradores de Luna (los genera Django).

## Riesgos / obligaciones
- Re-verificar disponibilidad al crear (anti doble-reserva). · Idempotencia. · No tocar modelos
  de ventas a ciegas (AR-034) → reusar el camino web. · Todo en modo "Deborah aprueba" (sin auto-write).

**Contexto:** H-011 (disponibilidad), H-027 (multinoche), [[modelos VentaReserva/ReservaServicio/Cliente]].
