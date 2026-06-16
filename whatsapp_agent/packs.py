"""Composición de itinerarios multi-servicio para el agente (H-015).

Nivel 1: Tina + Masaje el mismo día. Reglas (de Jorge):
- La masajista viene de otra ciudad → el masaje nuevo se agenda lo MÁS CERCA posible
  de un masaje YA reservado ese día (minimizar hueco muerto). Si no hay masajes ese día,
  el masaje va pegado a la tina (minimizar la espera del cliente).
- Tina y masaje NO se solapan (para la misma persona).
- Precio: tina + masaje (por persona); el PackDescuento (si aplica) lo calcula la capa de packs.

Las funciones de horario/clustering son puras (testeables sin DB/LLM).
"""

import logging

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers puros de horario / clustering
# ---------------------------------------------------------------------------

def hhmm_a_min(s):
    """'14:30' -> 870 ; None/invalid -> None."""
    try:
        h, m = str(s).strip().split(':')
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def min_a_hhmm(m):
    """870 -> '14:30'."""
    m = int(m)
    return f'{m // 60:02d}:{m % 60:02d}'


def no_solapan(a_ini, a_dur, b_ini, b_dur):
    """True si los bloques [a_ini, a_ini+a_dur) y [b_ini, b_ini+b_dur) NO se solapan."""
    return (a_ini + a_dur) <= b_ini or (b_ini + b_dur) <= a_ini


def elegir_slot_masaje(candidatos_min, masajes_agendados_min, tina_ini_min):
    """Elige el slot de masaje (en minutos) según el criterio de Jorge.

    - Si hay masajes agendados ese día → el candidato MÁS CERCANO a alguno de ellos
      (clustering: compactar la jornada de la masajista).
    - Si no hay → el candidato más cercano al inicio de la tina (pegado, minimiza espera).
    Devuelve el slot elegido (min) o None si no hay candidatos.
    """
    if not candidatos_min:
        return None
    if masajes_agendados_min:
        return min(candidatos_min,
                   key=lambda c: min(abs(c - x) for x in masajes_agendados_min))
    return min(candidatos_min, key=lambda c: abs(c - tina_ini_min))


def _slots_compatibles(slots_masaje_min, tina_ini_min, tina_dur, masaje_dur):
    """Slots de masaje que NO se solapan con el bloque de la tina."""
    return [s for s in slots_masaje_min
            if no_solapan(tina_ini_min, tina_dur, s, masaje_dur)]


# Combo cabaña + tina (Nivel 2): la tina del día del alojamiento NUNCA antes de las
# 16:00, y la regla fundamental (Jorge) es ofrecer el horario MÁS TARDE disponible.
TINA_PISO_CABANA_MIN = 16 * 60  # 16:00


def elegir_tina_mas_tarde(tinas_serv, piso_min=TINA_PISO_CABANA_MIN):
    """(tina_dict, 'HH:MM') de la tina disponible en el horario MÁS TARDE >= piso_min.

    Regla fundamental del combo cabaña+tina: prioridad al horario más tarde, con o sin
    hidromasaje. Empate de hora -> la más económica (precio_total), luego nombre, para
    ser determinístico. Devuelve (None, None) si ninguna tina tiene slot >= piso_min.
    """
    candidatos = []  # (slot_min, precio_total, nombre, tina, 'HH:MM')
    for t in (tinas_serv or []):
        for s in (t.get('slots_libres') or []):
            m = hhmm_a_min(s)
            if m is not None and m >= piso_min:
                candidatos.append((m, t.get('precio_total') or 0, t.get('nombre') or '', t, s))
    if not candidatos:
        return None, None
    candidatos.sort(key=lambda c: (-c[0], c[1], c[2]))  # hora desc, precio asc, nombre asc
    mejor = candidatos[0]
    return mejor[3], mejor[4]


# ---------------------------------------------------------------------------
# Composición (DB)
# ---------------------------------------------------------------------------

def _es_hidromasaje(nombre):
    """True si la tina lleva hidromasaje (gama más cara)."""
    return 'hidromasaje' in (nombre or '').lower()


def _pack_masaje_de_tina(tina_servicio_id):
    """ID del servicio de masaje que exige el 'Pack Tina X + Masaje' que contiene esta tina.

    Los packs tina+masaje usan `servicios_especificos` (una tina concreta + un masaje concreto).
    Para que el descuento aplique, el carrito debe llevar ESE masaje, no cualquiera (un masaje
    cualquiera no lo cuenta el motor de packs). Devuelve el servicio_id del masaje del pack, o
    None si la tina no participa en ningún pack tina+masaje.
    """
    from ventas.models import PackDescuento
    try:
        packs = (PackDescuento.objects
                 .filter(activo=True, usa_servicios_especificos=True,
                         servicios_especificos__id=tina_servicio_id)
                 .prefetch_related('servicios_especificos')
                 .distinct())
        for pack in packs:
            masaje = next((s for s in pack.servicios_especificos.all()
                           if (s.tipo_servicio or '') == 'masaje'), None)
            if masaje:
                return masaje.id
    except Exception:  # noqa: BLE001 — si falla, simplemente no hay descuento
        logger.exception('Pack: no se pudo resolver el masaje del pack de la tina %s', tina_servicio_id)
    return None


def _descuento_pack(tina, masaje_id, masaje_nombre, masaje_pp, f, tina_hora, masaje_hora, personas):
    """Descuento (int CLP) del PackDescuento para 1 tina (grupo) + N masajes (1 por persona)."""
    try:
        from ventas.services.pack_descuento_service import PackDescuentoService
        cart = [{
            'id': tina['servicio_id'], 'nombre': tina['nombre'],
            'precio': float(tina['precio_por_persona']),
            'fecha': f.isoformat(), 'hora': tina_hora,
            'cantidad_personas': personas, 'tipo_servicio': 'tina',
        }]
        for _ in range(max(1, personas)):
            cart.append({
                'id': masaje_id, 'nombre': masaje_nombre, 'precio': float(masaje_pp),
                'fecha': f.isoformat(), 'hora': masaje_hora, 'cantidad_personas': 1,
                'tipo_servicio': 'masaje',
            })
        packs_ap = PackDescuentoService.detectar_packs_aplicables(cart)
        return int(sum(float(p.get('descuento') or 0) for p in packs_ap))
    except Exception:  # noqa: BLE001 — el descuento es opcional; nunca romper la composición
        logger.exception('Pack: no se pudo calcular el descuento')
        return 0


def _componer_opcion(tinas_grupo, etiqueta, f, personas, agendados, masaje_por_id,
                     union_slots, masaje_generico):
    """Compone UNA opción (tina + masaje) para un grupo de tinas (con o sin hidromasaje).

    Para cada tina del grupo busca el masaje de SU pack (para que aplique el descuento) y, si
    ese masaje tiene cupo, encaja un slot compatible (clustering, sin solapar). Si la tina no
    tiene pack o su masaje no tiene cupo, cae al masaje genérico disponible (sin descuento).
    Devuelve el dict de la opción, o None si ninguna tina del grupo encaja.
    """
    agendados_set = set(agendados)
    for t in tinas_grupo:
        t_dur = t.get('duracion_min') or 0
        if not t.get('slots_libres'):
            continue

        # Masaje del pack de esta tina (si existe y tiene cupo ese día → aplica descuento).
        pack_masaje_id = _pack_masaje_de_tina(t['servicio_id'])
        m = masaje_por_id.get(pack_masaje_id) if pack_masaje_id else None
        if m:
            slots_masaje = sorted({hhmm_a_min(s) for s in (m.get('slots_libres') or [])
                                   if hhmm_a_min(s) is not None})
            masaje_dur = m.get('duracion_min') or 0
            masaje_id, masaje_nombre, masaje_pp = m['servicio_id'], m['nombre'], m['precio_por_persona']
        else:
            slots_masaje = union_slots
            masaje_dur = masaje_generico.get('duracion_min') or 0
            masaje_id = masaje_generico['servicio_id']
            masaje_nombre = masaje_generico['nombre']
            masaje_pp = masaje_generico['precio_por_persona']

        for t_slot in t['slots_libres']:
            t_ini = hhmm_a_min(t_slot)
            if t_ini is None:
                continue
            compat = _slots_compatibles(slots_masaje, t_ini, t_dur, masaje_dur)
            # Excluir slots con masaje ya agendado (la masajista ya está ocupada ahí).
            compat = [s for s in compat if s not in agendados_set]
            m_slot = elegir_slot_masaje(compat, agendados, t_ini)
            if m_slot is None:
                continue

            masaje_hora = min_a_hhmm(m_slot)
            masaje_total = masaje_pp * personas
            precio_total = t['precio_total'] + masaje_total
            descuento = _descuento_pack(t, masaje_id, masaje_nombre, masaje_pp,
                                        f, t_slot, masaje_hora, personas)
            precio_con_descuento = max(0, precio_total - descuento)
            return {
                'etiqueta': etiqueta,
                'tina': {
                    'nombre': t['nombre'], 'hora': t_slot,
                    'duracion_texto': t['duracion_texto'],
                    'precio_total': t['precio_total'],
                    'precio_por_persona': t['precio_por_persona'],
                },
                'masaje': {
                    'nombre': masaje_nombre, 'hora': masaje_hora, 'cantidad': personas,
                    'precio_total': masaje_total,
                },
                'orden': 'masaje antes de la tina' if m_slot < t_ini else 'masaje después de la tina',
                'clustering': bool(agendados),
                'precio_total': precio_total,                 # precio real (sin descuento)
                'descuento_pack': descuento,                  # 0 si no aplica
                'precio_con_descuento': precio_con_descuento,  # lo que paga si aplica el pack
                'hay_descuento': descuento > 0,
            }
    return None


def disponibilidad_pack_tina_masaje(fecha, personas=2):
    """Propone itinerarios Tina + Masaje para `fecha` y `personas`.

    Devuelve DOS alternativas para que el cliente elija sin una pregunta extra (Jorge):
    una tina CON hidromasaje (gama mayor) + masaje y otra SIN hidromasaje (más económica) +
    masaje. Cada opción usa el masaje de su pack para que el descuento aplique, y trae precio
    real y precio con descuento. None/errores si no se puede componer.
    """
    from .availability import disponibilidad, _parse_fecha

    f = _parse_fecha(fecha) if fecha else None
    if f is None:
        return {'error': 'fecha inválida (usa YYYY-MM-DD)'}

    # 1) Tinas con cupo para el grupo.
    tinas = disponibilidad(f, personas, 'tina').get('servicios', [])
    if not tinas:
        return {'fecha': f.isoformat(), 'personas': personas, 'opciones': [],
                'nota': 'no hay tinas con cupo ese día para esa cantidad de personas'}

    # 2) Masajes con cupo (1 persona por masaje): mapa por servicio_id + unión de slots (fallback).
    masajes_serv = disponibilidad(f, 1, 'masaje').get('servicios', [])
    if not masajes_serv:
        return {'fecha': f.isoformat(), 'personas': personas, 'opciones': [],
                'nota': 'no hay masajes con cupo ese día'}
    masaje_por_id = {m['servicio_id']: m for m in masajes_serv}
    union_slots = sorted({hhmm_a_min(s) for m in masajes_serv for s in (m.get('slots_libres') or [])
                          if hhmm_a_min(s) is not None})
    masaje_generico = masajes_serv[0]

    # 3) Masajes YA agendados ese día (para el clustering de la masajista).
    from ventas.models import ReservaServicio
    agendados = [hhmm_a_min(h) for h in (
        ReservaServicio.objects
        .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=f)
        .exclude(venta_reserva__estado_pago='cancelado')
        .values_list('hora_inicio', flat=True)
    )]
    agendados = [x for x in agendados if x is not None]

    # 4) Dos opciones: con hidromasaje (mayor valor) y sin hidromasaje (más económica).
    con = [t for t in tinas if _es_hidromasaje(t['nombre'])]
    sin = [t for t in tinas if not _es_hidromasaje(t['nombre'])]
    opciones = []
    for grupo, etiqueta in ((con, 'con hidromasaje'), (sin, 'sin hidromasaje')):
        op = _componer_opcion(grupo, etiqueta, f, personas, agendados,
                              masaje_por_id, union_slots, masaje_generico)
        if op:
            opciones.append(op)

    nota = ''
    if not opciones:
        nota = ('hay tinas pero no se pudo encajar el masaje sin solapar; '
                'ofrecer la tina y coordinar el masaje con una persona')

    # Upsell determinístico: si NINGUNA opción trae descuento (p.ej. fin de semana, el pack
    # es dom-jue), el código entrega el texto listo para que Luna lo incluya tal cual (más
    # confiable que pedírselo al modelo con una condición).
    nota_upsell = ''
    if opciones and not any(o['hay_descuento'] for o in opciones):
        nota_upsell = ('Este día queda a precio normal; el descuento de pack aplica de '
                       'domingo a jueves. Ofrece cotizar un día entre semana para que vea el ahorro.')

    return {'fecha': f.isoformat(), 'personas': personas, 'opciones': opciones,
            'nota': nota, 'nota_upsell': nota_upsell}


# ---------------------------------------------------------------------------
# Nivel 2: Cabaña + Tina (1 noche, 2 personas)
# ---------------------------------------------------------------------------

def _desayuno_de_cabana(cabana_nombre):
    """Servicio de desayuno NOMINAL de la cabaña: 'Cabaña Torre' -> 'Desayuno Torre'.

    Los desayunos se venden con el nombre de la cabaña (Jorge). Los nominales están
    despublicados (no salen en el catálogo suelto), así que se buscan por nombre, no por
    `publicado_web`. Precio plano $20.000 para dos. Devuelve dict o None.
    """
    from ventas.models import Servicio
    token = (cabana_nombre or '').split()[-1].strip() if cabana_nombre else ''
    if not token:
        return None
    try:
        d = (Servicio.objects.filter(activo=True, tipo_servicio='otro', nombre__icontains='desayuno')
             .filter(nombre__icontains=token).first()
             or Servicio.objects.filter(activo=True, nombre__iexact='Desayuno').first())
    except Exception:  # noqa: BLE001 — el desayuno es opcional; nunca romper la composición
        logger.exception('Pack cabaña: no se pudo resolver el desayuno de %s', cabana_nombre)
        return None
    if not d:
        return None
    return {'servicio_id': d.id, 'nombre': d.nombre, 'precio_total': int(d.precio_base), 'hora': '10:00'}


def _descuento_pack_cabana(cabana, tina, f, cabana_hora, tina_hora, personas):
    """Descuento (int CLP) del PackDescuento para 1 cabaña + 1 tina (ambas para `personas`).

    El pack de alojamiento se valida por tipo (no por servicios específicos) y exige
    >= 2 personas en cabaña y >= 2 en tina, misma fecha. Devuelve 0 si no aplica.
    """
    try:
        from ventas.services.pack_descuento_service import PackDescuentoService
        cart = [
            {'id': cabana['servicio_id'], 'nombre': cabana['nombre'],
             'precio': float(cabana['precio_por_persona']), 'fecha': f.isoformat(),
             'hora': cabana_hora, 'cantidad_personas': personas, 'tipo_servicio': 'cabana'},
            {'id': tina['servicio_id'], 'nombre': tina['nombre'],
             'precio': float(tina['precio_por_persona']), 'fecha': f.isoformat(),
             'hora': tina_hora, 'cantidad_personas': personas, 'tipo_servicio': 'tina'},
        ]
        packs_ap = PackDescuentoService.detectar_packs_aplicables(cart)
        return int(sum(float(p.get('descuento') or 0) for p in packs_ap))
    except Exception:  # noqa: BLE001 — el descuento es opcional; nunca romper la composición
        logger.exception('Pack cabaña: no se pudo calcular el descuento')
        return 0


def disponibilidad_pack_cabana_tina(fecha, personas=2):
    """Propone itinerarios Cabaña + Tina (1 noche, 2 personas) para `fecha`.

    Lista las cabañas libres esa noche (todas para 2) y les acopla UNA tina en el horario
    MÁS TARDE disponible >= 16:00 (regla fundamental). Cada opción trae precio real y precio
    con descuento de pack (dom-jue). El desayuno ($20.000 para dos, día siguiente ~10:00) se
    incluye por opción pero Luna solo lo ofrece si el cliente pregunta. 1 noche por ahora.
    """
    from .availability import disponibilidad, _parse_fecha

    f = _parse_fecha(fecha) if fecha else None
    if f is None:
        return {'error': 'fecha inválida (usa YYYY-MM-DD)'}
    personas = 2  # las cabañas son siempre para 2 (Jorge)

    cabanas = disponibilidad(f, personas, 'cabana').get('servicios', [])
    if not cabanas:
        return {'fecha': f.isoformat(), 'personas': personas, 'opciones': [],
                'nota': 'no hay cabañas libres esa noche para 2 personas'}

    # Tina del día del alojamiento: la más tarde disponible >= 16:00 (con o sin hidromasaje).
    tinas = disponibilidad(f, personas, 'tina').get('servicios', [])
    tina, tina_hora = elegir_tina_mas_tarde(tinas)

    opciones = []
    for c in cabanas:
        cabana_hora = (c.get('slots_libres') or ['16:00'])[0]   # check-in
        cab_total = c['precio_total']
        desayuno = _desayuno_de_cabana(c['nombre'])
        op = {
            'cabana': {'nombre': c['nombre'], 'hora_check_in': '16:00',
                       'hora_check_out': '11:00 del día siguiente', 'precio_total': cab_total},
            'desayuno': desayuno,            # solo ofrecer si el cliente pregunta
        }
        if tina is not None:
            tina_total = tina['precio_total']
            precio_total = cab_total + tina_total
            descuento = _descuento_pack_cabana(c, tina, f, cabana_hora, tina_hora, personas)
            op.update({
                'tina': {'nombre': tina['nombre'], 'hora': tina_hora, 'precio_total': tina_total},
                'precio_total': precio_total,
                'descuento_pack': descuento,
                'precio_con_descuento': max(0, precio_total - descuento),
                'hay_descuento': descuento > 0,
            })
        else:
            op.update({
                'tina': None,
                'precio_total': cab_total,
                'descuento_pack': 0,
                'precio_con_descuento': cab_total,
                'hay_descuento': False,
            })
        opciones.append(op)

    nota = ''
    if tina is None:
        nota = ('no hay tina disponible desde las 16:00 esa noche; ofrecer solo la cabaña '
                'y coordinar la tina con una persona')

    # Upsell determinístico: si hay combo (tina) pero ninguna opción trae descuento
    # (fin de semana / martes cerrado), el código entrega el aviso listo para Luna.
    nota_upsell = ''
    if opciones and tina is not None and not any(o['hay_descuento'] for o in opciones):
        nota_upsell = ('Este día queda a precio normal; el descuento del pack cabaña+tina aplica '
                       'de domingo a jueves. Ofrece cotizar un día entre semana para que vea el ahorro.')

    return {'fecha': f.isoformat(), 'personas': personas, 'tina_mas_tarde': tina_hora,
            'opciones': opciones, 'nota': nota, 'nota_upsell': nota_upsell}
