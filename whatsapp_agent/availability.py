"""Servicio de disponibilidad para el agente IA (H-011 / Fase A).

Función central que el agente consultará (vía tool-calling): dado tipo + fecha +
cantidad de personas, devuelve los servicios PUBLICADOS que admiten esa cantidad y
sus horarios libres ese día. REÚSA el motor de disponibilidad que ya existe (no
reinventa): slots por fecha + bloqueos de día/slot + capacidad + reservas del día.

Fuente de verdad de lo ofrecible: `publicado_web` + `activo` (decisión de Jorge),
igual que el grounding. Capacidad estricta por `capacidad_minima/maxima`.
"""

import logging
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

TIPOS_VALIDOS = {'tina', 'masaje', 'cabana', 'otro'}

# Las masajistas vienen desde la ciudad (~1h). Para HOY, si todavía no hay masajistas
# trabajando, no se puede ofrecer un masaje antes de que alcancen a llegar.
TRAVEL_MASAJISTA_MIN = 60


def _parse_fecha(fecha):
    """Acepta date o 'YYYY-MM-DD'. Devuelve date o None."""
    if hasattr(fecha, 'year') and hasattr(fecha, 'month'):
        return fecha
    try:
        return datetime.strptime(str(fecha).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def _hhmm_min(s):
    """'14:30' -> 870 ; None/inválido -> None."""
    try:
        h, m = str(s).strip().split(':')
        return int(h) * 60 + int(m)
    except (ValueError, AttributeError):
        return None


def _hay_masaje_agendado_hoy(f):
    """True si ya hay al menos un masaje agendado (no cancelado) ese día → masajistas en sitio."""
    from ventas.models import ReservaServicio
    return (ReservaServicio.objects
            .filter(servicio__tipo_servicio='masaje', fecha_agendamiento=f)
            .exclude(venta_reserva__estado_pago='cancelado')
            .exists())


def disponibilidad(fecha=None, personas=1, tipo=None):
    """Servicios publicados que admiten `personas`, con precio total y horarios libres.

    Con `fecha` (YYYY-MM-DD) → calcula horarios libres ese día (modo disponibilidad).
    Sin `fecha` → modo SOLO PRECIO: lista los servicios que aplican por capacidad con su
    precio total, sin horarios (para preguntas de precio sin fecha; H-011 refinamiento).

    Returns dict:
      { 'fecha', 'personas', 'tipo', 'solo_precio', 'servicios': [
            {nombre, precio_por_persona, es_por_persona, precio_total,
             capacidad_minima, capacidad_maxima, duracion_texto, slots_libres:[...]|null}
        ], 'error'? }
    """
    from ventas.models import Servicio, ServicioBloqueo, ServicioSlotBloqueo
    from ventas.calendar_utils import verificar_disponibilidad
    from ventas.views.calendario_matriz_view import extraer_slots_para_fecha

    from .grounding import formatear_duracion

    f = _parse_fecha(fecha) if fecha not in (None, '') else None
    if fecha not in (None, '') and f is None:
        return {'error': 'fecha inválida (usa formato YYYY-MM-DD)', 'servicios': []}

    try:
        personas = int(personas)
    except (TypeError, ValueError):
        personas = 1
    if personas < 1:
        personas = 1

    from .models import WhatsAppAgentConfig
    comp_ids = WhatsAppAgentConfig.get_solo().ids_complementarios()

    qs = Servicio.objects.filter(
        publicado_web=True, activo=True,
        capacidad_minima__lte=personas,
        capacidad_maxima__gte=personas,
    ).exclude(id__in=comp_ids)  # H-011: no ofrecer complementos como principales
    if tipo:
        tipo = str(tipo).strip().lower()
        if tipo in TIPOS_VALIDOS:
            qs = qs.filter(tipo_servicio=tipo)
    qs = qs.order_by('tipo_servicio', 'nombre')

    # Piso horario para HOY: nunca ofrecer horas pasadas. Se calcula una vez.
    ahora = timezone.localtime()
    es_hoy = (f == ahora.date()) if f is not None else False
    ahora_min = (ahora.hour * 60 + ahora.minute) if es_hoy else None
    # Para masajes hoy, si aún no hay masajistas en sitio, sumar el viaje (~1h).
    masaje_en_sitio = _hay_masaje_agendado_hoy(f) if es_hoy else False

    servicios = []
    for s in qs:
        libres = None
        if f is not None:
            # Modo disponibilidad: horarios libres ese día.
            if ServicioBloqueo.servicio_bloqueado_en_fecha(s.id, f):
                continue
            # Piso: hoy no se ofrecen horas pasadas; masaje sin masajistas en sitio
            # exige el tiempo de viaje (clientes vienen de otra ciudad).
            piso_min = None
            if es_hoy:
                piso_min = ahora_min
                if s.tipo_servicio == 'masaje' and not masaje_en_sitio:
                    piso_min = ahora_min + TRAVEL_MASAJISTA_MIN
            slots = extraer_slots_para_fecha(s.slots_disponibles, f) or []
            libres = []
            for hora in slots:
                if piso_min is not None:
                    hm = _hhmm_min(hora)
                    if hm is not None and hm < piso_min:
                        continue  # hora pasada (o sin margen de viaje) → no ofrecer
                if ServicioSlotBloqueo.slot_bloqueado(s.id, f, hora):
                    continue
                try:
                    if verificar_disponibilidad(s, f, hora, personas):
                        libres.append(hora)
                except Exception:  # noqa: BLE001 — un slot con error no debe tumbar la consulta
                    logger.exception('disponibilidad: error verificando %s %s %s', s.id, f, hora)
            if not libres:
                continue  # sin horarios ese día → no se ofrece

        # Precio POR PERSONA en TODOS los servicios (tina/masaje/cabaña): total = base × personas.
        precio_pp = int(s.precio_base)
        # Duración: cabañas se expresan "por noche", no en horas (H-011 refinamiento).
        duracion_texto = 'por noche' if s.tipo_servicio == 'cabana' else formatear_duracion(s.duracion)
        servicios.append({
            'nombre': s.nombre,
            'servicio_id': s.id,
            'precio_por_persona': precio_pp,
            'es_por_persona': True,
            'precio_total': precio_pp * personas,
            'capacidad_minima': s.capacidad_minima,
            'capacidad_maxima': s.capacidad_maxima,
            'duracion_texto': duracion_texto,
            'duracion_min': s.duracion or 0,
            'tipo': s.tipo_servicio,
            'slots_libres': libres,
        })

    return {
        'fecha': f.isoformat() if f else None,
        'personas': personas,
        'tipo': tipo or 'todos',
        'solo_precio': f is None,
        'servicios': servicios,
    }
