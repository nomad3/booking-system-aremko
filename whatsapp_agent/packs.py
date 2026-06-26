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


# Buffer máximo (min) entre tina y masaje según el cliente (Jorge, 2026-06-24):
#   - Cliente de CIUDAD (solo tina+masaje, sin alojamiento): espera en el lugar, sin
#     dónde estar → buffer corto, mismo bloque horario.
#   - Huésped (Ritual / con cabaña): espera en su cabaña → tolera buffers amplios; eso
#     lo resuelve `disponibilidad_ritual` por otra ruta, no esta función.
BUFFER_CIUDAD_MAX = 45   # tina+masaje sin alojamiento: nunca dejar al cliente esperando más


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


def _gap_min(tina_ini, tina_dur, masaje_ini, masaje_dur):
    """Minutos de espera entre tina y masaje (van pegados → 0). Asume que no se solapan."""
    return max(masaje_ini - (tina_ini + tina_dur), tina_ini - (masaje_ini + masaje_dur))


def _componer_opcion(tinas_grupo, etiqueta, f, personas, agendados, masaje_por_id,
                     union_slots, masaje_generico, buffer_max=None):
    """Compone UNA opción (tina + masaje) para un grupo de tinas (con o sin hidromasaje).

    Para cada tina del grupo busca el masaje de SU pack (para que aplique el descuento) y, si
    ese masaje tiene cupo, encaja un slot compatible (clustering, sin solapar). Si la tina no
    tiene pack o su masaje no tiene cupo, cae al masaje genérico disponible (sin descuento).
    `buffer_max` (min) acota la espera entre tina y masaje (cliente de ciudad); None = sin tope.
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
            # Cliente de ciudad: descartar masajes lejos de la tina (no lo hagas esperar).
            if buffer_max is not None:
                compat = [s for s in compat
                          if _gap_min(t_ini, t_dur, s, masaje_dur) <= buffer_max]
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


def disponibilidad_pack_tina_masaje(fecha, personas=2, buffer_max=BUFFER_CIUDAD_MAX):
    """Propone itinerarios Tina + Masaje para `fecha` y `personas`.

    Devuelve DOS alternativas para que el cliente elija sin una pregunta extra (Jorge):
    una tina CON hidromasaje (gama mayor) + masaje y otra SIN hidromasaje (más económica) +
    masaje. Cada opción usa el masaje de su pack para que el descuento aplique, y trae precio
    real y precio con descuento. None/errores si no se puede componer.

    Es el caso CIUDAD (sin alojamiento): `buffer_max` (min) acota la espera entre tina y
    masaje para no dejar al cliente esperando en el lugar; los huéspedes van por el Ritual.
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
                              masaje_por_id, union_slots, masaje_generico,
                              buffer_max=buffer_max)
        if op:
            opciones.append(op)

    nota = ''
    if not opciones:
        nota = ('no quedó un masaje cerca de la tina (a menos de {}min) sin solapar; '
                'ofrecer la tina y coordinar el masaje con una persona, o proponer otro día'
                .format(buffer_max) if buffer_max is not None else
                'hay tinas pero no se pudo encajar el masaje sin solapar; '
                'ofrecer la tina y coordinar el masaje con una persona')

    # Limitar a máximo 2 opciones para evitar que Luna ofrezca demasiadas alternativas
    opciones = opciones[:2]

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
    con descuento de pack (dom-jue). El desayuno ($20.000 para dos, día siguiente ~10:00) va
    INCLUIDO en el `precio_total` del paquete y se menciona como incluido. 1 noche por ahora.
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
    # limite=None: el tope de 2 podía dejar fuera las tinas con slot >=16:00 (mismo bug del Ritual).
    tinas = disponibilidad(f, personas, 'tina', limite=None).get('servicios', [])
    tina, tina_hora = elegir_tina_mas_tarde(tinas)

    opciones = []
    for c in cabanas:
        cabana_hora = (c.get('slots_libres') or ['16:00'])[0]   # check-in
        cab_total = c['precio_total']
        desayuno = _desayuno_de_cabana(c['nombre'])
        desayuno_total = int(desayuno['precio_total']) if desayuno else 0
        op = {
            'cabana': {'nombre': c['nombre'], 'hora_check_in': '16:00',
                       'hora_check_out': '11:00 del día siguiente', 'precio_total': cab_total},
            'desayuno': desayuno,            # INCLUIDO en el precio del paquete (no es opcional)
            'desayuno_incluido': True,
        }
        if tina is not None:
            tina_total = tina['precio_total']
            precio_total = cab_total + tina_total + desayuno_total
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
                'precio_total': cab_total + desayuno_total,
                'descuento_pack': 0,
                'precio_con_descuento': cab_total + desayuno_total,
                'hay_descuento': False,
            })
        opciones.append(op)

    # Limitar a máximo 2 opciones para evitar que Luna ofrezca demasiadas alternativas
    opciones = opciones[:2]

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


# ── Ritual del Río (H-031 Fase 1): cabaña + tina + masaje + desayuno, 1 unidad ──

RITUAL_PRECIO_PLANO = 240000          # precio normal (viernes y sábado)
RITUAL_PRECIO_DOMJUE = 210000         # precio promocional domingo a jueves
RITUAL_DIAS_DOMJUE = (0, 1, 3, 4)     # 0=Dom..6=Sáb (esquema PackDescuento); Mar(2) cerrado, Vie/Sáb normal
RITUAL_DESCUENTO_PREMIUM = 10000      # descuento por cada componente premium (Torre / tina hidromasaje)

# Horarios de masaje RESERVADOS al Programa Ritual/Refugio (Jorge, 2026-06-26). El masaje de
# estos programas SOLO puede caer en uno de estos 4 horarios; el resto de los slots del Masaje
# queda libre para masaje solo o pack tina+masaje (ciudad). La "hora río" (15:30) es la ancla
# por defecto: es ANTES del check-in (16:00) a propósito —el cliente llega un poco antes, se
# hace el masaje y luego se instala en la cabaña. La constante canónica vive en availability.py
# (allí disponibilidad() los excluye por defecto para ciudad/solo); acá solo se aliasan.
from .availability import (
    MASAJE_SLOTS_PROGRAMA as PROGRAMA_MASAJE_SLOTS,
    MASAJE_SLOTS_PROGRAMA_MIN as PROGRAMA_MASAJE_SLOTS_MIN,
)
RITUAL_MASAJE_HORA_RIO_MIN = 15 * 60 + 30   # 15:30 — ancla cuando no hay otro masaje al que pegarse


def _precio_objetivo_ritual(f):
    """Precio objetivo del Ritual según el día: $210.000 dom-jue, $240.000 viernes/sábado.
    El descuento dom-jue (vs el precio normal) lo absorbe la línea 'Descuento de servicios'."""
    dia = (f.weekday() + 1) % 7        # 0=Dom..6=Sáb, igual que PackDescuento
    return RITUAL_PRECIO_DOMJUE if dia in RITUAL_DIAS_DOMJUE else RITUAL_PRECIO_PLANO


def _normalizar_servicios(servicios):
    """De la lista que dijo el cliente a un set de tipos: alojamiento / tina / masaje."""
    from .availability import _sin_acentos
    s = set()
    for item in (servicios or []):
        t = _sin_acentos(str(item))
        if 'aloj' in t or 'cabana' in t:
            s.add('alojamiento')
        if 'tina' in t or 'tinaj' in t or 'hidromasaje' in t:
            s.add('tina')
        if 'masaj' in t:
            s.add('masaje')
    return s


def router_disponibilidad(servicios, fecha, personas=2):
    """ENRUTADOR determinístico (H-031): según los servicios que mencionó el cliente,
    elige la rama del árbol y arma el itinerario COMPLETO. Evita que Luna ofrezca a
    medias (ej. omitir el masaje) o elija mal la herramienta — Luna solo lista lo que
    pidió el cliente, el código decide la rama.
    """
    from .availability import disponibilidad
    s = _normalizar_servicios(servicios)
    aloj, tina, masaje = 'alojamiento' in s, 'tina' in s, 'masaje' in s

    if aloj and tina and masaje:                       # 🌙 Ritual del Río (desayuno incluido)
        return dict(disponibilidad_ritual(fecha), rama='ritual')
    if aloj and tina:                                  # Alojamiento + Tina (+desayuno)
        return dict(disponibilidad_pack_cabana_tina(fecha), rama='alojamiento_tina')
    if aloj and masaje:                                # Alojamiento + Masaje (gap): ofrece ambos + sugiere Ritual
        return {
            'rama': 'alojamiento_masaje',
            'cabanas': disponibilidad(fecha, personas, 'cabana'),
            'masajes': disponibilidad(fecha, personas, 'masaje'),
            'sugerencia': 'Si suma una tina, queda el Ritual del Río completo '
                          '(alojamiento + tina + masaje + desayuno) por $240.000.',
        }
    if aloj:                                           # Cabaña sola (+desayuno)
        return dict(disponibilidad(fecha, personas, 'cabana'), rama='alojamiento')
    if tina and masaje:                                # Tina + Masaje
        return dict(disponibilidad_pack_tina_masaje(fecha, personas), rama='tina_masaje')
    if tina:                                           # Tina sola
        return dict(disponibilidad(fecha, personas, 'tina'), rama='tina')
    if masaje:                                          # Masaje solo
        return dict(disponibilidad(fecha, personas, 'masaje'), rama='masaje')
    return {'rama': None,
            'error': 'No identifiqué los servicios. Pregunta si busca alojamiento, tina y/o masaje.'}


def _es_cabana_torre(nombre):
    return 'torre' in (nombre or '').lower()


def _elegir_cabana_ritual(cabanas, preferir_torre=False):
    """Prefiere una cabaña que NO sea Torre (protege margen); usa Torre solo si es la única
    opción. Con `preferir_torre=True` (solo para verificación/forzado) elige Torre si hay.
    Devuelve (cabana, es_torre) o (None, False)."""
    torre = [c for c in cabanas if _es_cabana_torre(c.get('nombre', ''))]
    no_torre = [c for c in cabanas if not _es_cabana_torre(c.get('nombre', ''))]
    if preferir_torre and torre:
        return torre[0], True
    if no_torre:
        return no_torre[0], False
    if cabanas:
        return cabanas[0], True   # solo quedaba Torre
    return None, False


def _masajes_agendados_min(f):
    """Horas (en minutos) de los masajes ya agendados ese día (no cancelados), para compactar
    la jornada de la masajista (clustering)."""
    from ventas.models import ReservaServicio
    horas = (ReservaServicio.objects
             .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=f)
             .exclude(venta_reserva__estado_pago='cancelado')
             .values_list('hora_inicio', flat=True))
    return [m for m in (hhmm_a_min(h) for h in horas) if m is not None]


def _elegir_masaje_ritual(masajes, f):
    """Devuelve (masaje, hora) del masaje del Programa Ritual/Refugio.

    El masaje SOLO puede caer en uno de los horarios del programa (PROGRAMA_MASAJE_SLOTS) que
    esté LIBRE ese día. Entre los libres elige por proximidad a un masaje ya agendado (clustering,
    para compactar a la masajista); si no hay ninguno agendado, ancla a la "hora río" (15:30).
    Manda el programa: nunca sale de esos 4 horarios. Devuelve (None, None) si ninguno está libre.
    """
    agendados = _masajes_agendados_min(f)
    for m in masajes:
        libres = sorted({hhmm_a_min(s) for s in (m.get('slots_libres') or [])
                         if hhmm_a_min(s) in PROGRAMA_MASAJE_SLOTS_MIN})
        if not libres:
            continue
        if agendados:
            elegido = min(libres, key=lambda c: min(abs(c - x) for x in agendados))
        else:
            elegido = min(libres, key=lambda c: abs(c - RITUAL_MASAJE_HORA_RIO_MIN))
        return m, min_a_hhmm(elegido)
    return None, None


def _es_tina_hidromasaje(nombre):
    return 'hidromasaje' in (nombre or '').lower()


def _elegir_tina_ritual(tinas, preferir_hidromasaje=False):
    """Prefiere una tina ESTÁNDAR (sin hidromasaje, para no gatillar descuento); si
    solo hay hidromasaje, la usa. Con `preferir_hidromasaje=True` (solo verificación/forzado)
    elige hidromasaje si hay. Dentro del tipo elegido, la más tarde >=16:00.
    Devuelve (tina, hora, es_hidromasaje)."""
    estandar = [t for t in tinas if not _es_tina_hidromasaje(t.get('nombre', ''))]
    hidro = [t for t in tinas if _es_tina_hidromasaje(t.get('nombre', ''))]
    orden = ((hidro, True), (estandar, False)) if preferir_hidromasaje else ((estandar, False), (hidro, True))
    for grupo, es_hidro in orden:
        t, hora = elegir_tina_mas_tarde(grupo)
        if t is not None:
            return t, hora, es_hidro
    return None, None, False


def disponibilidad_ritual(fecha, preferir_premium=False):
    """Itinerario ÚNICO del Ritual del Río para `fecha` (2 personas, 1 noche).

    Reusa la disponibilidad existente, sin servicios ni slots nuevos:
      - Cabaña: una disponible que NO sea Torre; Torre solo como última opción.
      - Tina: la más tarde disponible >= 16:00 (lógica cabaña+tina).
      - Masaje para 2: un slot existente a partir de las 16:00.
      - Desayuno: el de esa cabaña.
    Precio $240.000 PLANO. Si toca Torre y/o hidromasaje (+$10k c/u), `confirmar_ritual`
    aplica el descuento para mantener el total. Devuelve disponible=False (con nota para
    ofrecer otra fecha) si falta cualquiera de las 3 patas.

    `preferir_premium=True` fuerza Torre + hidromasaje SI hay (solo para verificación del
    descuento; el flujo normal de Luna usa False = lo más barato, para proteger margen).
    """
    from .availability import disponibilidad, _parse_fecha

    f = _parse_fecha(fecha) if fecha else None
    if f is None:
        return {'error': 'fecha inválida (usa YYYY-MM-DD)'}
    personas = 2

    # limite=None: ver TODAS las cabañas libres (el tope alfabético de 2 dejaba "Torre"
    # —última alfabéticamente— siempre fuera, así que nunca se podía elegir como último recurso).
    cabanas = disponibilidad(f, personas, 'cabana', limite=None).get('servicios', [])
    cabana, es_torre = _elegir_cabana_ritual(cabanas, preferir_torre=preferir_premium)
    if cabana is None:
        return {'fecha': f.isoformat(), 'disponible': False,
                'nota': 'no hay cabañas libres esa noche para el ritual; ofrece otra fecha'}

    # limite=None: ver TODAS las tinas libres. El tope de 2 (1 sin + 1 con hidromasaje,
    # alfabético) dejaba fuera las que SÍ tienen slot >=16:00 (p.ej. Puntiagudo/Tronador) y
    # podía elegir 2 cuyos únicos slots eran <16:00 → falso "no hay tina desde las 16:00".
    tinas = disponibilidad(f, personas, 'tina', limite=None).get('servicios', [])
    tina, tina_hora, es_hidromasaje = _elegir_tina_ritual(tinas, preferir_hidromasaje=preferir_premium)
    if tina is None:
        return {'fecha': f.isoformat(), 'disponible': False,
                'nota': 'no hay tina disponible desde las 16:00 esa noche; ofrece otra fecha'}

    # limite=None: ver todos los masajes. incluir_slots_programa=True: el programa SÍ puede usar
    # los 4 horarios reservados (15:30/18:00/20:30/21:45), que para ciudad/solo están excluidos.
    masajes = disponibilidad(f, personas, 'masaje', limite=None,
                             incluir_slots_programa=True).get('servicios', [])
    masaje, masaje_hora = _elegir_masaje_ritual(masajes, f)
    if masaje is None:
        return {'fecha': f.isoformat(), 'disponible': False,
                'nota': 'no hay masaje para 2 en los horarios del programa (15:30/18:00/20:30/21:45) '
                        'esa noche; ofrece otra fecha'}

    # Precio objetivo del día ($210k dom-jue, $240k vie/sáb). El descuento es lo que haya que
    # restar de la suma de componentes para llegar al objetivo (incluye el ahorro dom-jue y el
    # extra de cualquier componente premium). confirmar_ritual lo aplica con la línea
    # "Descuento de servicios" (precio_base negativo, cantidad = monto del descuento).
    objetivo = _precio_objetivo_ritual(f)
    suma = ((cabana.get('precio_total') or 0) + (tina.get('precio_total') or 0)
            + (masaje.get('precio_total') or 0))
    descuento = max(0, int(suma) - objetivo)
    es_domjue = objetivo == RITUAL_PRECIO_DOMJUE

    return {
        'fecha': f.isoformat(),
        'disponible': True,
        'personas': personas,
        'precio_total': objetivo,
        'es_domjue': es_domjue,
        'es_torre': es_torre,
        'es_hidromasaje': es_hidromasaje,
        'descuento': descuento,
        'itinerario': {
            'cabana': {'servicio_id': cabana.get('servicio_id'), 'nombre': cabana['nombre'],
                       'hora_check_in': '16:00', 'es_torre': es_torre},
            'tina': {'servicio_id': tina.get('servicio_id'), 'nombre': tina['nombre'],
                     'hora': tina_hora, 'es_hidromasaje': es_hidromasaje},
            'masaje': {'servicio_id': masaje.get('servicio_id'), 'nombre': masaje['nombre'], 'hora': masaje_hora},
            'desayuno': _desayuno_de_cabana(cabana['nombre']),
        },
        'nota_descuento': (f'Precio domingo a jueves ${objetivo:,.0f} (promoción).'
                           if es_domjue else f'Precio fin de semana ${objetivo:,.0f}.'),
    }


def _servicio_descuento():
    """El Servicio 'Descuento de servicios' (precio_base negativo, normalmente -1) que se usa
    como línea de ajuste para clavar totales. Devuelve el Servicio o None."""
    from ventas.models import Servicio
    return (Servicio.objects.filter(nombre__icontains='descuento de servicios').first()
            or Servicio.objects.filter(nombre__icontains='descuento').order_by('id').first())


def construir_servicios_ritual(fecha, preferir_premium=False):
    """Arma la lista de servicios del Ritual para `preparar_reserva`, clavando el total en el
    precio objetivo del día ($210.000 dom-jue / $240.000 vie-sáb) (H-031 pieza 3, escritura).
    `preferir_premium` solo para verificación (fuerza Torre+hidromasaje si hay, para ver la
    línea de descuento); el flujo normal usa False.

    Reusa `disponibilidad_ritual` (misma cabaña/tina/masaje que se le ofreció al cliente) y
    devuelve servicios=[{servicio_id, fecha, hora, cantidad_personas}, ...] listos para la
    propuesta. El desayuno YA va incluido en el precio de la cabaña (Jorge), así que NO es una
    línea aparte. El descuento se calcula como (suma_componentes − objetivo) y se aplica con la
    línea 'Descuento de servicios' (precio_base negativo), de modo que el total quede SIEMPRE en
    el objetivo del día sin depender de cuánto sume cada componente premium.

    Devuelve dict con servicios + total, o {'disponible': False, ...} / {'error': ...}.
    """
    from ventas.models import Servicio

    r = disponibilidad_ritual(fecha, preferir_premium=preferir_premium)
    if r.get('error'):
        return {'error': r['error']}
    if not r.get('disponible'):
        return {'disponible': False, 'fecha': r.get('fecha'), 'nota': r.get('nota')}

    it = r['itinerario']
    f_iso = r['fecha']
    personas = r.get('personas', 2)
    cab, tina, masaje = it['cabana'], it['tina'], it['masaje']

    def _pb(servicio_id):
        s = Servicio.objects.filter(id=servicio_id).first()
        return int(s.precio_base) if s else 0

    # Cabaña (incluye desayuno) + tina + masaje, todos para `personas`.
    servicios = [
        {'servicio_id': cab['servicio_id'], 'fecha': f_iso,
         'hora': cab.get('hora_check_in', '16:00'), 'cantidad_personas': personas},
        {'servicio_id': tina['servicio_id'], 'fecha': f_iso,
         'hora': tina['hora'], 'cantidad_personas': personas},
        {'servicio_id': masaje['servicio_id'], 'fecha': f_iso,
         'hora': masaje['hora'], 'cantidad_personas': personas},
    ]
    from .availability import _parse_fecha
    objetivo = _precio_objetivo_ritual(_parse_fecha(f_iso))
    suma = sum(_pb(s['servicio_id']) * s['cantidad_personas'] for s in servicios)
    descuento = max(0, suma - objetivo)

    if descuento:
        ds = _servicio_descuento()
        if ds is None:
            return {'error': 'no existe el servicio "Descuento de servicios" para clavar el total'}
        pb = int(ds.precio_base)
        if pb >= 0:
            return {'error': f'el servicio de descuento tiene precio_base {pb} (debería ser negativo)'}
        # cantidad tal que precio_base * cantidad = -descuento (con precio_base -1 → cantidad=descuento)
        cantidad = round(descuento / abs(pb))
        servicios.append({'servicio_id': ds.id, 'fecha': f_iso,
                          'hora': cab.get('hora_check_in', '16:00'), 'cantidad_personas': cantidad})

    return {
        'disponible': True,
        'fecha': f_iso,
        'personas': personas,
        'servicios': servicios,
        'suma_componentes': suma,
        'descuento': descuento,
        'total': suma - descuento,            # = objetivo ($210k dom-jue / $240k vie-sáb)
        'objetivo': objetivo,
        'es_domjue': r.get('es_domjue'),
        'itinerario': it,
        'es_torre': r.get('es_torre'),
        'es_hidromasaje': r.get('es_hidromasaje'),
    }


# ── Refugio Aremko: el Ritual del Río en estadía de 2 NOCHES (misma cabaña) ──
# Noche 1 = el Ritual (cabaña + tina + masaje + desayuno). Noche 2 = la misma cabaña
# (+ desayuno). UNA sola tina y UN solo masaje en toda la estadía. Precio PLANO todos
# los días (incluye desayuno). El descuento clava el total como en el Ritual.

REFUGIO_PRECIO_PLANO = 290000   # 2 noches, misma cabaña, plano todos los días
REFUGIO_NOCHES = 2


def disponibilidad_refugio(fecha, preferir_premium=False):
    """Itinerario del Refugio Aremko para `fecha` de llegada (2 personas, 2 noches).

    Reusa lo del Ritual + la disponibilidad multinoche: una cabaña libre las DOS noches
    seguidas (misma cabaña), tina y masaje la PRIMERA noche (≥16:00), desayuno incluido
    ambas mañanas. Precio $290.000 plano. `preferir_premium` solo para verificación.
    Devuelve itinerario único o disponible=False (con nota para ofrecer otra fecha).
    """
    from datetime import timedelta
    from .availability import disponibilidad, _parse_fecha

    f1 = _parse_fecha(fecha) if fecha else None
    if f1 is None:
        return {'error': 'fecha inválida (usa YYYY-MM-DD)'}
    personas = 2
    f2 = f1 + timedelta(days=1)            # segunda noche
    f_salida = f1 + timedelta(days=REFUGIO_NOCHES)

    # Cabañas libres AMBAS noches (misma cabaña): intersección por servicio_id, sin tope.
    cab1 = disponibilidad(f1, personas, 'cabana', limite=None).get('servicios', [])
    cab2 = disponibilidad(f2, personas, 'cabana', limite=None).get('servicios', [])
    ids2 = {c.get('servicio_id') for c in cab2}
    ambas = [c for c in cab1 if c.get('servicio_id') in ids2]
    cabana, es_torre = _elegir_cabana_ritual(ambas, preferir_torre=preferir_premium)
    if cabana is None:
        return {'fecha': f1.isoformat(), 'disponible': False,
                'nota': 'no hay una cabaña libre las 2 noches seguidas; ofrece otra fecha'}

    # UNA tina CADA día (las dos noches) + UN masaje la primera noche.
    tinas1 = disponibilidad(f1, personas, 'tina', limite=None).get('servicios', [])
    tina1, tina1_hora, es_hidro1 = _elegir_tina_ritual(tinas1, preferir_hidromasaje=preferir_premium)
    if tina1 is None:
        return {'fecha': f1.isoformat(), 'disponible': False,
                'nota': 'no hay tina disponible la primera noche; ofrece otra fecha'}
    tinas2 = disponibilidad(f2, personas, 'tina', limite=None).get('servicios', [])
    tina2, tina2_hora, es_hidro2 = _elegir_tina_ritual(tinas2, preferir_hidromasaje=preferir_premium)
    if tina2 is None:
        return {'fecha': f1.isoformat(), 'disponible': False,
                'nota': 'no hay tina disponible la segunda noche; ofrece otra fecha'}

    masajes = disponibilidad(f1, personas, 'masaje', limite=None,
                             incluir_slots_programa=True).get('servicios', [])
    masaje, masaje_hora = _elegir_masaje_ritual(masajes, f1)
    if masaje is None:
        return {'fecha': f1.isoformat(), 'disponible': False,
                'nota': 'no hay masaje para 2 la primera noche en los horarios del programa '
                        '(15:30/18:00/20:30/21:45); ofrece otra fecha'}

    # Suma cruda: 2 noches de cabaña + 2 tinas (una por día) + 1 masaje. Descuento la lleva a $290.000.
    suma = (2 * (cabana.get('precio_total') or 0) + (tina1.get('precio_total') or 0)
            + (tina2.get('precio_total') or 0) + (masaje.get('precio_total') or 0))
    descuento = max(0, int(suma) - REFUGIO_PRECIO_PLANO)

    return {
        'fecha': f1.isoformat(),
        'fecha_salida': f_salida.isoformat(),
        'disponible': True,
        'personas': personas,
        'noches': REFUGIO_NOCHES,
        'precio_total': REFUGIO_PRECIO_PLANO,
        'descuento': descuento,
        'es_torre': es_torre,
        'es_hidromasaje': es_hidro1 or es_hidro2,
        'itinerario': {
            'cabana': {'servicio_id': cabana.get('servicio_id'), 'nombre': cabana['nombre'],
                       'hora_check_in': '16:00', 'noches': REFUGIO_NOCHES, 'es_torre': es_torre},
            'tina': {'servicio_id': tina1.get('servicio_id'), 'nombre': tina1['nombre'],
                     'hora': tina1_hora, 'noche': 1, 'fecha': f1.isoformat(), 'es_hidromasaje': es_hidro1},
            'tina2': {'servicio_id': tina2.get('servicio_id'), 'nombre': tina2['nombre'],
                      'hora': tina2_hora, 'noche': 2, 'fecha': f2.isoformat(), 'es_hidromasaje': es_hidro2},
            'masaje': {'servicio_id': masaje.get('servicio_id'), 'nombre': masaje['nombre'], 'hora': masaje_hora},
            'desayuno': _desayuno_de_cabana(cabana['nombre']),
        },
        'nota': (f'2 noches en {cabana["nombre"]} (llegada {f1.isoformat()}, '
                 f'salida {f_salida.isoformat()}); tina caliente cada día, masaje la primera noche.'),
    }


def construir_servicios_refugio(fecha, preferir_premium=False):
    """Arma la lista de servicios del Refugio para `preparar_reserva`, clavando el total en
    $290.000. La cabaña va DOS veces (noche 1 y noche 2, MISMO servicio_id) + 1 tina + 1 masaje
    la primera noche. El desayuno va incluido en la cabaña. El descuento = (suma − $290.000)
    con la línea 'Descuento de servicios'. Devuelve servicios listos o disponible=False/error.
    """
    from datetime import timedelta
    from ventas.models import Servicio
    from .availability import _parse_fecha

    r = disponibilidad_refugio(fecha, preferir_premium=preferir_premium)
    if r.get('error'):
        return {'error': r['error']}
    if not r.get('disponible'):
        return {'disponible': False, 'fecha': r.get('fecha'), 'nota': r.get('nota')}

    it = r['itinerario']
    f1 = _parse_fecha(r['fecha'])
    f2 = f1 + timedelta(days=1)
    personas = r.get('personas', 2)
    cab, tina, tina2, masaje = it['cabana'], it['tina'], it['tina2'], it['masaje']

    def _pb(servicio_id):
        s = Servicio.objects.filter(id=servicio_id).first()
        return int(s.precio_base) if s else 0

    servicios = [
        # MISMA cabaña las 2 noches (mismo servicio_id, fechas consecutivas).
        {'servicio_id': cab['servicio_id'], 'fecha': f1.isoformat(),
         'hora': '16:00', 'cantidad_personas': personas},
        {'servicio_id': cab['servicio_id'], 'fecha': f2.isoformat(),
         'hora': '16:00', 'cantidad_personas': personas},
        # Una tina caliente CADA día.
        {'servicio_id': tina['servicio_id'], 'fecha': f1.isoformat(),
         'hora': tina['hora'], 'cantidad_personas': personas},
        {'servicio_id': tina2['servicio_id'], 'fecha': f2.isoformat(),
         'hora': tina2['hora'], 'cantidad_personas': personas},
        # Un masaje para 2, la primera noche.
        {'servicio_id': masaje['servicio_id'], 'fecha': f1.isoformat(),
         'hora': masaje['hora'], 'cantidad_personas': personas},
    ]
    suma = sum(_pb(s['servicio_id']) * s['cantidad_personas'] for s in servicios)
    descuento = max(0, suma - REFUGIO_PRECIO_PLANO)

    if descuento:
        ds = _servicio_descuento()
        if ds is None:
            return {'error': 'no existe el servicio "Descuento de servicios" para clavar el total'}
        pb = int(ds.precio_base)
        if pb >= 0:
            return {'error': f'el servicio de descuento tiene precio_base {pb} (debería ser negativo)'}
        cantidad = round(descuento / abs(pb))
        servicios.append({'servicio_id': ds.id, 'fecha': f1.isoformat(),
                          'hora': '16:00', 'cantidad_personas': cantidad})

    return {
        'disponible': True,
        'fecha': r['fecha'],
        'fecha_salida': r.get('fecha_salida'),
        'personas': personas,
        'noches': REFUGIO_NOCHES,
        'servicios': servicios,
        'suma_componentes': suma,
        'descuento': descuento,
        'total': suma - descuento,            # = REFUGIO_PRECIO_PLANO ($290.000)
        'objetivo': REFUGIO_PRECIO_PLANO,
        'itinerario': it,
        'es_torre': r.get('es_torre'),
        'es_hidromasaje': r.get('es_hidromasaje'),
    }
