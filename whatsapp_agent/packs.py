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
