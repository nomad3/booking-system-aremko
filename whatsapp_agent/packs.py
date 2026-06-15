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


# ---------------------------------------------------------------------------
# Composición (DB)
# ---------------------------------------------------------------------------

def disponibilidad_pack_tina_masaje(fecha, personas=2):
    """Propone un itinerario Tina + Masaje para `fecha` y `personas`.

    Devuelve dict con la tina elegida, el/los masaje(s) y los horarios, listo para que el
    agente lo ofrezca como borrador. None/errores si no se puede componer.
    """
    from .availability import disponibilidad, _parse_fecha
    from .models import WhatsAppAgentConfig

    f = _parse_fecha(fecha) if fecha else None
    if f is None:
        return {'error': 'fecha inválida (usa YYYY-MM-DD)'}

    # 1) Tinas con cupo para el grupo.
    tina_res = disponibilidad(f, personas, 'tina')
    tinas = tina_res.get('servicios', [])
    if not tinas:
        return {'fecha': f.isoformat(), 'personas': personas, 'tina': None, 'masaje': None,
                'nota': 'no hay tinas con cupo ese día para esa cantidad de personas'}

    # 2) Masajes con cupo (1 persona por masaje) + slots libres.
    masaje_res = disponibilidad(f, 1, 'masaje')
    masajes_serv = masaje_res.get('servicios', [])
    slots_masaje = sorted({hhmm_a_min(s) for m in masajes_serv for s in (m.get('slots_libres') or [])
                           if hhmm_a_min(s) is not None})
    masaje_dur = max((m.get('duracion_min') or 0) for m in masajes_serv) if masajes_serv else 60

    # 3) Masajes YA agendados ese día (para el clustering).
    from ventas.models import ReservaServicio
    agendados = [hhmm_a_min(h) for h in (
        ReservaServicio.objects
        .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=f)
        .exclude(venta_reserva__estado_pago='cancelado')
        .values_list('hora_inicio', flat=True)
    )]
    agendados = [x for x in agendados if x is not None]

    # 4) Elegir tina + slot de masaje compatible (no solapa) con clustering.
    elegido = None
    for t in tinas:
        t_dur = t.get('duracion_min') or 0
        for t_slot in (t.get('slots_libres') or []):
            t_ini = hhmm_a_min(t_slot)
            if t_ini is None:
                continue
            compat = _slots_compatibles(slots_masaje, t_ini, t_dur, masaje_dur)
            # Excluir los slots que YA tienen un masaje agendado: ahí la masajista está
            # ocupada (un masaje nuevo necesitaría otra masajista en el mismo momento).
            # El clustering pega el nuevo al más cercano LIBRE de esos agendados.
            agendados_set = set(agendados)
            compat = [s for s in compat if s not in agendados_set]
            m_slot = elegir_slot_masaje(compat, agendados, t_ini)
            if m_slot is not None:
                elegido = (t, t_slot, t_ini, t_dur, m_slot)
                break
        if elegido:
            break

    if not elegido:
        # Hay tinas pero no se pudo encajar un masaje sin solape (o no hay masajes libres).
        t = tinas[0]
        return {
            'fecha': f.isoformat(), 'personas': personas,
            'tina': {'nombre': t['nombre'], 'horarios': t['slots_libres'],
                     'precio_total': t['precio_total'], 'duracion_texto': t['duracion_texto']},
            'masaje': None,
            'nota': 'hay tina, pero no se pudo encajar el masaje sin solapar (sin cupo de masaje compatible)',
        }

    t, t_slot, t_ini, t_dur, m_slot = elegido
    m0 = masajes_serv[0] if masajes_serv else None
    masaje_pp = (m0['precio_por_persona'] if m0 else 0)
    masaje_total = masaje_pp * personas
    precio_total = t['precio_total'] + masaje_total

    # Descuento del pack (PackDescuento): se arma un carrito (1 tina para el grupo + 1 masaje
    # por persona = N instancias, que es lo que pide el pack tina+masaje) y se consulta el motor.
    descuento = 0
    try:
        from ventas.services.pack_descuento_service import PackDescuentoService
        cart = [{
            'id': t['servicio_id'], 'nombre': t['nombre'], 'precio': float(t['precio_por_persona']),
            'fecha': f.isoformat(), 'hora': t_slot, 'cantidad_personas': personas, 'tipo_servicio': 'tina',
        }]
        if m0:
            for _ in range(max(1, personas)):
                cart.append({
                    'id': m0['servicio_id'], 'nombre': m0['nombre'], 'precio': float(masaje_pp),
                    'fecha': f.isoformat(), 'hora': min_a_hhmm(m_slot), 'cantidad_personas': 1,
                    'tipo_servicio': 'masaje',
                })
        packs_ap = PackDescuentoService.detectar_packs_aplicables(cart)
        descuento = int(sum(float(p.get('descuento') or 0) for p in packs_ap))
    except Exception:  # noqa: BLE001 — el descuento es opcional; nunca romper la composición
        logger.exception('Pack: no se pudo calcular el descuento')
        descuento = 0

    precio_con_descuento = max(0, precio_total - descuento)

    return {
        'fecha': f.isoformat(),
        'personas': personas,
        'tina': {
            'nombre': t['nombre'],
            'hora': t_slot,
            'duracion_texto': t['duracion_texto'],
            'precio_total': t['precio_total'],
            'precio_por_persona': t['precio_por_persona'],
        },
        'masaje': {
            'hora': min_a_hhmm(m_slot),
            'cantidad': personas,
            'descripcion': f'{personas} masaje(s), uno por persona',
            'paralelo_o_secuencial': 'según masajistas disponibles ese día',
            'precio_total': masaje_total,
        },
        'orden': 'masaje antes de la tina' if m_slot < t_ini else 'masaje después de la tina',
        'clustering': bool(agendados),
        # Precios YA calculados (no recalcular en el modelo):
        'precio_total': precio_total,                 # precio real (sin descuento)
        'descuento_pack': descuento,                  # 0 si no aplica
        'precio_con_descuento': precio_con_descuento,  # lo que paga si aplica el pack
        'precio_por_persona_con_descuento': precio_con_descuento // max(1, personas),
        'hay_descuento': descuento > 0,
    }
