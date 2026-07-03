# -*- coding: utf-8 -*-
"""Elegibilidad y resumen de reservas EXISTENTES para que Luna pueda agregar
servicios/productos a una reserva YA CREADA (H-060).

Funciones puras: reciben datos ya extraídos de VentaReserva/ReservaServicio/
ReservaProducto (dicts simples), no tocan la BD — así se testean en
whatsapp_agent/tests/test_logic.py sin Django (mismo criterio que packs.py/availability.py).
"""

from datetime import timedelta

# Días DESPUÉS de la fecha del servicio en los que la reserva sigue siendo elegible
# para agregar algo (ej. cliente escribe al día siguiente de su visita). 0 = solo hoy
# en adelante; el default de 1 cubre "escribió al otro día" sin abrir la ventana de más.
RESERVA_ELEGIBLE_DIAS_GRACIA = 1


def es_reserva_elegible(reserva_dict, hoy):
    """reserva_dict: {'estado_pago': str, 'fechas_servicios': [date, ...]}. `hoy`: date.

    Elegible si:
    - NO está cancelada (estado_pago != 'cancelado'), Y
    - no tiene ningún ReservaServicio con fecha (ej. reserva solo de productos) → elegible
      igual, O al menos una fecha de servicio es >= hoy - RESERVA_ELEGIBLE_DIAS_GRACIA (una
      reserva con servicios pasados Y futuros es elegible por el futuro, no se descarta entera).
    """
    if reserva_dict.get('estado_pago') == 'cancelado':
        return False
    fechas = reserva_dict.get('fechas_servicios') or []
    if not fechas:
        return True
    limite = hoy - timedelta(days=RESERVA_ELEGIBLE_DIAS_GRACIA)
    return any(f >= limite for f in fechas)


def resumen_corto_reserva(reserva_dict):
    """Arma 'Tina Llaima + Masaje Relajación (04-07-2026)' a partir de
    reserva_dict['items']: [{'tipo': 'servicio'|'producto', 'nombre': str, 'fecha': date|None}].
    Sin paréntesis si ningún item trae fecha (ej. reserva solo de productos)."""
    items = reserva_dict.get('items') or []
    nombres = [it['nombre'] for it in items if it.get('nombre')]
    texto = ' + '.join(nombres) if nombres else 'Reserva'
    fechas = [it['fecha'] for it in items if it.get('fecha')]
    if fechas:
        texto += f" ({min(fechas).strftime('%d-%m-%Y')})"
    return texto


def filtrar_reservas_elegibles(reservas, hoy):
    """Filtra las NO elegibles + ordena por fecha_principal ascendente (más próxima
    primero; las sin fecha quedan al final). Devuelve copias de los dicts con
    'fecha_principal' y 'resumen_corto' agregados, listas para serializar en la
    respuesta del endpoint."""
    resultado = []
    for r in reservas:
        if not es_reserva_elegible(r, hoy):
            continue
        items = r.get('items') or []
        fechas = [it['fecha'] for it in items if it.get('fecha')]
        nuevo = dict(r)
        nuevo['fecha_principal'] = min(fechas) if fechas else None
        nuevo['resumen_corto'] = resumen_corto_reserva(r)
        resultado.append(nuevo)
    resultado.sort(key=lambda r: (r['fecha_principal'] is None, r['fecha_principal'] or hoy))
    return resultado
