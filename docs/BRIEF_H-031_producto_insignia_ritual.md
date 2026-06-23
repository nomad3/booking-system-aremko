# BRIEF H-031 — Producto insignia "Noche de ritual junto al río" (sistema: Luna + agendamiento + pre-llegada)

**Contexto:** Plan estratégico de Aremko ("Plan Río", iniciativa PR-01). El producto insignia es el **ritual completo 3-en-1** (único en Puerto Varas con alojamiento+tina+masaje juntos), vivido de noche, junto al río, para parejas. Es la triple de mayor valor de los datos (~$256k promedio) convertida en una experiencia con nombre. Necesitamos que el **sistema** lo soporte para que Luna lo ofrezca, lo agende y prepare la llegada.

## Oferta (cerrada por Jorge 2026-06-19)
- Componentes (2 pax): cabaña/noche $90.000 + tina $50.000 + **masaje nocturno** $80.000 + desayuno $20.000.
- **Precio del ritual: $240.000** (= la suma; sin descuento). La "capa de experiencia" (bienvenida sensorial, circuito térmico, recuerdo, desayuno gourmet) va incluida como valor agregado, NO baja el precio.
- 2 personas (parejas). **Capacidad: 5 rituales por noche.** El masaje nocturno usa los horarios de los **slots de masaje existentes**.

## Outcome buscado
1. Luna puede **ofrecer y armar "Noche de ritual junto al río"** como una experiencia de un clic (no pedir los 4 ítems por separado).
2. Luna prepara la llegada capturando datos pre-visita (Foso del sistema digital de Aremko).

## Fase 1 — El ritual como paquete de un clic (CERO ROCE)
**Directriz de Jorge (importante):** se vende EL PAQUETE como una sola unidad. Luna lo agenda **completo de una** (cabaña + tina + masaje nocturno + desayuno) — **NADA de ir servicio por servicio**. Cero roce.
- **Mecanismo:** reusar el MISMO que ya funciona y está configurado para **alojamiento + tina**; lo único que falta es **agregar el masaje en los horarios disponibles** (los horarios ya viven en los **slots de masaje**). No reinventar — usar los mismos criterios de alojamiento+tina.
- Luna ofrece el ritual como upsell cuando piden cabaña o tina ("¿quieren vivir el ritual completo de los 5 sentidos junto al río?"). Al aceptar → agenda el **paquete entero** a $240.000, 2 pax, en una sola acción.
- **Capacidad: 5 rituales por noche.**

## Fase 1 — Diseño técnico (aremko-cli, 2026-06-22, tras leer el código Django)

Leí `whatsapp_agent/packs.py`, `availability.py`, `agent.py` y el flujo de carrito (`carrito_reservas` + `reserva_service.py`). **~80% ya existe; el "un clic" es ensamblar, no construir.** Propuesta concreta:

### Lo que se reutiliza tal cual (no tocar)
- **`disponibilidad_pack_cabana_tina(fecha)`** (`packs.py`) — ya coordina **cabaña + tina** misma noche (cabañas libres 2 pax + tina acoplada + check-in 16:00/out 11:00 + desayuno). **Es la base del ritual; solo le falta la 3ª pata.**
- **`disponibilidad(fecha, 2, 'masaje')`** — ya devuelve slots de masaje. Clave que descubrí: la restricción "masajista en sitio" (`masaje_en_sitio`) **SOLO aplica a HOY** (`es_hoy`). Para fechas futuras (el ritual se reserva con antelación) el masaje se ofrece normal. Y `_es_masaje_agendable` ya habilita justo el masaje de **Relajación/Descontracturante** (el del ritual).
- **`confirmar_reserva_carrito` → `PropuestaReserva` → banner "Crear reserva" → `crear_reserva`** (H-028/H-029) — el "un clic" de cierre YA está resuelto: arma UNA propuesta con TODOS los ítems. Reusar entero.

### Las 3 piezas nuevas (todas en Django)
1. **`disponibilidad_ritual(fecha)`** (nueva en `packs.py`) — extiende `disponibilidad_pack_cabana_tina` con la pata de masaje: además de cabaña+tina, pide `disponibilidad(f, 2, 'masaje')` y arma **1 itinerario** si las 3 patas están libres esa noche. Si falta una → "no disponible esa fecha, te ofrezco estas otras". **Secuencia (decisión Jorge 2026-06-22): la función elige el combo que CALCE** — cualquier par tina+masaje de esa noche que no se solape; NO forzar la tina-más-tarde. Solo validar que el slot de tina y el de masaje no choquen y formen una tarde coherente (check-in 16:00 → los 2 servicios en sus slots → noche → desayuno ~10:00).
2. **Capacidad 5/noche SIN modelo nuevo** — el cuello más angosto es el masajista. Si el servicio "masaje nocturno" se configura con **5 slots/noche**, la disponibilidad del ritual queda **topada en 5 automáticamente** (reusa la lógica de slots que ya cuenta `ReservaServicio`). No hace falta flag ni tabla nueva.
3. **`confirmar_ritual(fecha)`** (nueva tool, `agent.py`) — un solo tool determinístico: arma el carrito con los **4 ítems en los slots elegidos** (cabaña@16:00 + tina@slot + masaje@slot + desayuno) → `confirmar_reserva_carrito` → 1 propuesta → banner. Cero roce: Luna ofrece "el Ritual del Río para el [fecha], $240.000 para 2" y con un "sí" agenda todo.

### Precio (decisión Jorge 2026-06-22): **$240.000 PLANO todos los días**
- NO aplicar el descuento de pack dom-jue (`_descuento_pack_cabana`) al ritual — es producto insignia de precio fijo.
- $240k = la suma natural de los 4 ítems a precio real (90+50+80+20, para 2). Si se cargan los 4 al carrito a su precio, el total da $240k **sin lógica de precio especial** — solo hay que **saltar el descuento dom-jue** en este camino.

### Prompt de Luna
- Ofrecer el ritual como **1 unidad** (upsell al pedir cabaña/tina). Al aceptar → **una sola** llamada a `confirmar_ritual`. Prohibir ir servicio por servicio (cero roce). Mismo grounding duro de H-033 (solo lo que devuelve la tool).

### Config/datos a confirmar en Django (no código)
- ¿Cuál es el servicio "masaje nocturno" del ritual (Relajación) y ya tiene **slots nocturnos** cargados con **capacidad 5/noche**? (Jorge: los horarios ya viven en los slots de masaje.)
- Que el precio del masaje para 2 sea $80.000 (40k pp) para que la suma cuadre en $240k.

---

## Fase 2 — Pre-llegada (24h antes, vía Luna/WhatsApp)
Luna envía un mensaje de preparación y captura 3 cosas, que deben quedar **visibles para el staff** (bandeja o ficha de la reserva):
- **(a) Foto de la pareja** → para imprimirla y montarla como recuerdo en la cabaña.
- **(b) Preferencia de masaje** (presión suave/media/firme; aroma de aceite).
- **(c) Preferencia/restricción de desayuno.**

Texto sugerido del mensaje pre-llegada (editable):
> Hola [nombre] 🌿 Mañana los esperamos en Aremko para su **Noche de ritual junto al río**. Vivirán un **ritual de los 5 sentidos**: el sonido del Río Pescado y las aves, el aroma del bosque nativo, la contemplación del río, los sabores del sur en el desayuno y las manos expertas de nuestros masajistas.
> Su tina es un **circuito térmico**: ~15 min en agua caliente + breve salida al frío (no es un baño, es una terapia de desconexión).
> Para dejarlo a su medida: ¿masaje con presión suave/media/firme y aroma preferido? ¿alguna preferencia para el desayuno? ¿nos mandan una **foto de ustedes** para una sorpresa de bienvenida? 🤫

## Fuera de alcance de H-031
- **Gift card del ritual** → irá en la iniciativa PR-03 (handoff aparte).
- Insumos físicos / operación (aromaterapia, batas, impresión del recuerdo, desayuno gourmet) → lado Jorge, no sistema.

## Preguntas abiertas para django
1. ~~¿Reusar el flujo alojamiento+tina + agregar masaje?~~ **RESUELTO:** sí — ver "Fase 1 · Diseño técnico". `disponibilidad_ritual` extiende `disponibilidad_pack_cabana_tina` con la pata de masaje.
2. ~~¿El masaje ya es agendable?~~ **RESUELTO (leyendo código):** sí para fechas futuras (`_es_masaje_agendable` habilita Relajación/Descontracturante; la traba `masaje_en_sitio` solo aplica a HOY). Falta confirmar que el servicio de masaje nocturno tenga **slots nocturnos + capacidad 5/noche** cargados (config, no código).
3. **(sigue abierta)** ¿Dónde quedan visibles para el staff las 3 capturas pre-llegada (foto/masaje/desayuno)? ¿bandeja, ficha de reserva, ambas? — es de la **Fase 2**, no bloquea la Fase 1.

El diseño completo de la experiencia (5 sentidos, circuito térmico, recuerdo de madera, desayuno de la Patagonia) vive en el repo de estrategia de aremko-cli; lo comparto si necesitas más contexto. **Capacidad 5/noche y masaje en los slots existentes ya definidos por Jorge.**
