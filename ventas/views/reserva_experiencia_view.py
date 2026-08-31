"""Reservar y pagar las experiencias desde su landing (2026-08-30).

Decisión de Jorge: las landings VENDEN como prioridad y WhatsApp queda como
segunda opción, uniforme en todas. El precedente es «Cabaña y spa por el día»
(dia_reserva_view): carrito armado DIRECTO con el constructor de Luna, precio
blindado o no se paga, paquete cerrado sin doble descuento, pago completo por
Flow.

Este módulo generaliza ese camino con un registro: cada experiencia declara su
constructor (el MISMO que usa Luna por WhatsApp — no hay dos motores) y el
nombre de su landing. La integridad ya no es un monto fijo: es el `objetivo`
que el propio constructor declara (el Ritual vale $210.000 dom-jue y $240.000
vie-sáb; el que decide es el constructor, nunca esta vista).

El día NO se migró acá a propósito: está vivo en producción con sus pruebas y
su bloqueo de noche previa; se toca cuando haya una razón, no por prolijidad.
"""
from __future__ import annotations

import logging

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)


def _constructor_ritual(fecha):
    from whatsapp_agent.packs import construir_servicios_ritual
    return construir_servicios_ritual(fecha)


# Cada entrada: el constructor de Luna y la landing adonde volver explicando.
# La base pública no dibuja los mensajes de Django, así que el motivo viaja en
# la dirección — mismo patrón que el día.
EXPERIENCIAS = {
    'ritual': {
        'constructor': _constructor_ritual,
        'landing': 'ritual_rio_landing',
    },
}


def _volver(landing, motivo, fecha=''):
    destino = reverse(landing)
    query = f'?motivo={motivo}'
    if fecha:
        query += f'&fecha={fecha}'
    return redirect(destino + query)


def _reservar_paquete(request, clave):
    """Arma el paquete de la experiencia en el carrito y manda al checkout."""
    exp = EXPERIENCIAS[clave]
    landing = exp['landing']

    if request.method != 'POST':
        return redirect(reverse(landing))

    fecha = (request.POST.get('fecha') or '').strip()
    if not fecha:
        return _volver(landing, 'sin_fecha')

    # Fechas pasadas: el mismo candado que el calendario interno. Una noche
    # agendada hacia atrás no existe para nadie.
    try:
        from datetime import date as _date
        if _date.fromisoformat(fecha) < timezone.localdate():
            return _volver(landing, 'no_disponible', fecha)
    except ValueError:
        return _volver(landing, 'sin_fecha')

    try:
        armado = exp['constructor'](fecha)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[reservar %s] no se pudo armar el %s: %s',
                         clave, fecha, exc)
        return _volver(landing, 'error', fecha)

    if armado.get('error'):
        logger.error('[reservar %s] %s -> %s', clave, fecha, armado['error'])
        return _volver(landing, 'error', fecha)
    if not armado.get('disponible'):
        return _volver(landing, 'no_disponible', armado.get('fecha') or fecha)

    from ventas.models import Servicio

    servicios_cart = []
    for s in armado['servicios']:
        servicio = Servicio.objects.filter(id=s['servicio_id']).first()
        if servicio is None:
            logger.error('[reservar %s] falta el servicio %s del paquete del %s',
                         clave, s['servicio_id'], fecha)
            return _volver(landing, 'error', fecha)
        personas = s['cantidad_personas']
        servicios_cart.append({
            'id': servicio.id,
            'nombre': servicio.nombre,
            'precio': float(servicio.precio_base),
            'fecha': s['fecha'],
            'hora': s['hora'],
            'cantidad_personas': personas,
            'tipo_servicio': servicio.tipo_servicio,
            'subtotal': float(servicio.precio_base) * personas,
        })

    total = sum(i['subtotal'] for i in servicios_cart)
    objetivo = int(armado.get('objetivo') or 0)

    # Falla cerrado, contra el objetivo que DECLARÓ el constructor. Si un
    # precio del catálogo cambió bajo los pies, mandarla a pagar sería cobrar
    # un monto que nadie prometió. Preferible perder la venta.
    if not objetivo or round(total) != objetivo:
        logger.error('[reservar %s] el paquete del %s suma $%s y el objetivo '
                     'es $%s; no se manda a pagar', clave, fecha,
                     round(total), objetivo)
        return _volver(landing, 'precio', fecha)

    request.session['cart'] = {
        'servicios': servicios_cart,
        'giftcards': [],
        'productos': [],
        'total': total,
        # Apaga la detección de packs: el precio ya trae su descuento adentro.
        'paquete_cerrado': clave,
    }
    request.session.modified = True

    logger.info('[reservar %s] carrito armado para el %s: $%s (%s servicios)',
                clave, armado['fecha'], round(total), len(servicios_cart))
    return redirect('ventas:checkout')


def ritual_reservar_view(request):
    return _reservar_paquete(request, 'ritual')
