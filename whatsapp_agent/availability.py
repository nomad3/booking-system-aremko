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

logger = logging.getLogger(__name__)

TIPOS_VALIDOS = {'tina', 'masaje', 'cabana', 'otro'}


def _parse_fecha(fecha):
    """Acepta date o 'YYYY-MM-DD'. Devuelve date o None."""
    if hasattr(fecha, 'year') and hasattr(fecha, 'month'):
        return fecha
    try:
        return datetime.strptime(str(fecha).strip(), '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def disponibilidad(fecha, personas=1, tipo=None):
    """Servicios publicados que admiten `personas` y tienen horarios libres en `fecha`.

    Returns dict:
      { 'fecha', 'personas', 'tipo', 'servicios': [
            {nombre, precio, capacidad_minima, capacidad_maxima, duracion_min, slots_libres:[...]}
        ], 'error'? }
    """
    from ventas.models import Servicio, ServicioBloqueo, ServicioSlotBloqueo
    from ventas.calendar_utils import verificar_disponibilidad
    from ventas.views.calendario_matriz_view import extraer_slots_para_fecha

    f = _parse_fecha(fecha)
    if f is None:
        return {'error': 'fecha inválida (usa formato YYYY-MM-DD)', 'servicios': []}

    try:
        personas = int(personas)
    except (TypeError, ValueError):
        personas = 1
    if personas < 1:
        personas = 1

    qs = Servicio.objects.filter(
        publicado_web=True, activo=True,
        capacidad_minima__lte=personas,
        capacidad_maxima__gte=personas,
    )
    if tipo:
        tipo = str(tipo).strip().lower()
        if tipo in TIPOS_VALIDOS:
            qs = qs.filter(tipo_servicio=tipo)
    qs = qs.order_by('tipo_servicio', 'nombre')

    servicios = []
    for s in qs:
        # Día completo bloqueado (mantención/reparación).
        if ServicioBloqueo.servicio_bloqueado_en_fecha(s.id, f):
            continue
        slots = extraer_slots_para_fecha(s.slots_disponibles, f) or []
        libres = []
        for hora in slots:
            if ServicioSlotBloqueo.slot_bloqueado(s.id, f, hora):
                continue
            try:
                if verificar_disponibilidad(s, f, hora, personas):
                    libres.append(hora)
            except Exception:  # noqa: BLE001 — un slot con error no debe tumbar la consulta
                logger.exception('disponibilidad: error verificando %s %s %s', s.id, f, hora)
        if libres:
            servicios.append({
                'nombre': s.nombre,
                'precio': int(s.precio_base),
                'capacidad_minima': s.capacidad_minima,
                'capacidad_maxima': s.capacidad_maxima,
                'duracion_min': s.duracion,
                'slots_libres': libres,
            })

    return {
        'fecha': f.isoformat(),
        'personas': personas,
        'tipo': tipo or 'todos',
        'servicios': servicios,
    }
