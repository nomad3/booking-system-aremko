# BRIEF H-015 — Disponibilidad de PACKS multi-servicio para el agente Luna

- **Pedido por:** Jorge (directo) · 2026-06-15
- **Implementa:** Django (composición de itinerarios en el agente). aremko-cli solo muestra el borrador.
- **Contexto:** continúa H-011 (disponibilidad de UN servicio). Ahora Luna debe componer
  itinerarios de VARIOS servicios (packs), subiendo en complejidad de a un nivel.

## Principio
Luna da **borradores**; Deborah aprueba/edita antes de enviar. → el itinerario propuesto
debe ser coherente y realista, no perfecto (Deborah es la red de seguridad).

## Estado del sistema (de la investigación 2026-06-15)
- **Ya existe:** disponibilidad de 1 servicio (`verificar_disponibilidad`, con masajista),
  detección de packs con descuento (`PackDescuento` + `pack_descuento_service.detectar_packs_aplicables`),
  y `validar_disponibilidad` (Luna API) que valida una LISTA de servicios (aislados) + aplica packs.
- **NO existe:** (1) detección de choques de horario entre servicios de la misma persona;
  (2) disponibilidad de cabañas por NOCHES (hoy es slot-por-día, sin rango); (3) helper
  "masajistas libres a tal hora".

## Roadmap (menor → mayor complejidad)

### Nivel 1 — Tina + Masaje (mismo día)  ← EN CURSO
**Criterios de Jorge:**
- **Clustering de masajista (el corazón):** la masajista viene de otra ciudad; al agendar el
  masaje nuevo, ponerlo **lo más cerca posible de un masaje ya reservado ese día** (minimizar
  el hueco muerto de la masajista). A veces queda antes de la tina, a veces después. Si NO hay
  masajes agendados ese día, slot sensato libre.
- **Masajes 2+:** paralelo si hay masajistas libres; si no, secuencial. Según disponibilidad.
- **Holgura:** la que den los slots de cada servicio (sin buffer artificial).
- No solapar tina y masaje para la misma persona.
- Precio: tina + masaje (por persona) − `PackDescuento` si aplica.

**Algoritmo propuesto (a confirmar):**
1. Slots de tina libres (capacidad del grupo) ese día.
2. Slots de masaje libres + qué masajista libre por slot (helper nuevo).
3. Elegir slot de masaje: el más cercano a un masaje ya agendado ese día (clustering);
   si no hay → el que mejor calce con la tina.
4. Componer itinerario tina+masaje sin solape; 2+ masajes paralelo/secuencial según masajistas.
5. Precio total con `PackDescuento`.
6. Luna ofrece el itinerario en el borrador; Deborah aprueba/ajusta.

**A construir:** helper "masajistas libres en fecha+hora"; lógica de no-solape (fin = inicio +
duración); composición del itinerario con clustering; tool del agente `consultar_disponibilidad_pack`
(o extender la existente); reuso de `PackDescuento` para el precio.

### Nivel 2 — Cabaña + Tina
- Cabaña se razona por **noches** (rango de fechas) — NO existe hoy, hay que construirlo.
  La tina va en una noche de la estadía. Criterios a definir con Jorge.

### Nivel 3 — Cabaña + Tina + Masaje (completo)
- Itinerario completo a lo largo de la estadía; combina todo. + add-ons (desayuno, ambientaciones).

## Aceptación (Nivel 1)
Cliente pide "tina + masaje el sábado para 2" → Luna propone un itinerario coherente (tina a una
hora, masaje pegado al masaje más cercano ya agendado, sin solape) con el precio del pack, como
borrador para que Deborah apruebe.
