"""Reserva por la web del programa «Cabaña y spa por el día» (2026-08-29).

Nació de una venta perdida: una clienta entró a reservar y la página solo le
ofrecía escribir por WhatsApp. El programa se había dejado fuera del carrito a
propósito, por dos razones que siguen siendo ciertas:

  1. `add_to_cart` le reescribe a TODA cabaña la cantidad de personas a su
     capacidad máxima (AR-014). El paquete calcula los $200.000 con dos
     personas, así que pasando por ahí el cobro saldría más caro que el precio
     prometido.
  2. La noche anterior tiene que quedar bloqueada: la cabaña debe estar lista a
     las 10:00 y nadie puede tomarla la víspera.

Este módulo resuelve las dos sin tocar el carrito normal:

  · Arma el carrito DIRECTO con lo que devuelve `construir_servicios_dia()` —la
    misma función que usa Luna por WhatsApp—, de modo que la regla de AR-014
    nunca corre y los subtotales quedan tal como se calcularon.
  · Marca el carrito como `paquete_cerrado`, para que ningún descuento de pack
    se aplique encima de un precio que ya viene fijado.
  · Deja `cabana_id` y la fecha guardados en el carrito, que viaja hasta el
    webhook de Flow: ahí, con el pago confirmado, se bloquea la noche.

Regla dura: si el carrito armado no suma EXACTAMENTE el precio del programa, no
se manda a pagar. Es preferible perder la venta a cobrarle mal a una persona.
"""
from __future__ import annotations

import logging

from django.shortcuts import redirect
from django.urls import reverse

logger = logging.getLogger(__name__)


def _volver(motivo, fecha=''):
    """Devuelve a la landing explicando por qué, en vez de rebotar en silencio.

    La base pública no dibuja los mensajes de Django, así que un `messages.error`
    no se vería: la clienta volvería a la misma página sin entender nada. El
    motivo viaja en la dirección y la landing lo muestra.
    """
    destino = reverse('dia_landing')
    query = f'?motivo={motivo}'
    if fecha:
        query += f'&fecha={fecha}'
    return redirect(destino + query)


def dia_reservar_view(request):
    """Arma el paquete del día en el carrito y manda al checkout."""
    if request.method != 'POST':
        return redirect(reverse('dia_landing'))

    fecha = (request.POST.get('fecha') or '').strip()
    if not fecha:
        return _volver('sin_fecha')

    from whatsapp_agent.packs import DIA_PRECIO_PLANO, construir_servicios_dia

    try:
        armado = construir_servicios_dia(fecha)
    except Exception as exc:  # noqa: BLE001
        logger.exception('[dia_reservar] no se pudo armar el paquete del %s: %s', fecha, exc)
        return _volver('error', fecha)

    if armado.get('error'):
        logger.error('[dia_reservar] %s -> %s', fecha, armado['error'])
        return _volver('error', fecha)

    if not armado.get('disponible'):
        # Día no vendible (no es lun/mié/jue) o sin cupo. Ambos se le explican
        # a la clienta en la landing; no son lo mismo y no dan lo mismo.
        return _volver('no_disponible', armado.get('fecha') or fecha)

    from ventas.models import Servicio

    servicios_cart = []
    for s in armado['servicios']:
        servicio = Servicio.objects.filter(id=s['servicio_id']).first()
        if servicio is None:
            logger.error('[dia_reservar] falta el servicio %s del paquete del %s',
                         s['servicio_id'], fecha)
            return _volver('error', fecha)
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

    # Falla cerrado. Si acá el total no calza, algo cambió bajo los pies (un
    # precio editado en el admin, un servicio de descuento tocado) y mandarla a
    # pagar significaría cobrarle un monto que nadie prometió.
    if round(total) != DIA_PRECIO_PLANO:
        logger.error('[dia_reservar] el paquete del %s suma $%s y debería sumar $%s; '
                     'no se manda a pagar', fecha, round(total), DIA_PRECIO_PLANO)
        return _volver('precio', fecha)

    request.session['cart'] = {
        'servicios': servicios_cart,
        'giftcards': [],
        'productos': [],
        'total': total,
        # Marca que apaga la detección de packs: este precio ya viene con su
        # descuento adentro y aplicarle otro lo dejaría bajo lo que vale.
        'paquete_cerrado': 'dia',
        # Viaja hasta el webhook de Flow para bloquear la noche anterior.
        'dia_bloqueo': {
            'cabana_id': armado['cabana_id'],
            'fecha': armado['fecha'],
        },
    }
    request.session.modified = True

    logger.info('[dia_reservar] carrito armado para el %s: $%s (%s servicios)',
                armado['fecha'], round(total), len(servicios_cart))
    return redirect('ventas:checkout')
