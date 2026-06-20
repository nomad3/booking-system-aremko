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
1. Para el paquete de un clic, ¿lo más limpio es **reusar el flujo de alojamiento+tina ya configurado + agregar masaje en sus slots**? (Jorge: *"los mismos criterios que ya funcionan para alojamiento y tina; solo falta agregar masajes en los horarios disponibles"*.)
2. ¿El masaje ya es agendable dentro de ese flujo, o solo existe en los slots de masaje y hay que conectarlo?
3. ¿Dónde quedan visibles para el staff las 3 capturas pre-llegada (foto/masaje/desayuno)? ¿bandeja, ficha de reserva, ambas?

El diseño completo de la experiencia (5 sentidos, circuito térmico, recuerdo de madera, desayuno de la Patagonia) vive en el repo de estrategia de aremko-cli; lo comparto si necesitas más contexto. **Capacidad 5/noche y masaje en los slots existentes ya definidos por Jorge.**
