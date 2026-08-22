# -*- coding: utf-8 -*-
"""Las comandas siguen a la reserva cuando se mueve de fecha.

Caso real (Jorge, 2026-08-22, reserva 6586): la reserva nació el 14/08 para el
22/08 y el cliente la movió al 29/08. Los servicios se movieron; las dos
comandas de cocina quedaron ancladas al 22 (`fecha_entrega_objetivo` se fija
al crear la comanda y nadie la volvía a tocar) → aparecieron en la agenda del
22 con la cocina preparando una tabla para alguien que llega en una semana.

Regla: cuando un ReservaServicio cambia de fecha u hora, las comandas
PENDIENTES de esa reserva cuyo objetivo coincide EXACTAMENTE con el horario
viejo de ese servicio se mueven al horario nuevo. Solo esas: un pedido que un
huésped hizo desde la tina el segundo día de su estadía está anclado a «ese
momento», no a un servicio, y no debe moverse porque alguien corrió la cabaña.
"""
import logging
from datetime import datetime, time

from django.utils import timezone

logger = logging.getLogger(__name__)

# Comandas que cocina todavía no cerró: son las únicas que tiene sentido mover.
ESTADOS_QUE_SIGUEN = ('pendiente', 'procesando')


def objetivo_de(fecha, hora):
    """Pura. La MISMA composición fecha+hora con la que nacen los objetivos en
    los dos caminos que crean comandas (`_asegurar_comanda_de_productos` del
    admin y `_fecha_objetivo_de` del pedido del cliente): hora 'HH:MM' o 12:00
    si viene vacía o rara. Si no hay fecha, None."""
    if not fecha:
        return None
    try:
        h = datetime.strptime(str(hora or '12:00')[:5], '%H:%M').time()
    except (ValueError, TypeError):
        h = time(12, 0)
    return timezone.make_aware(datetime.combine(fecha, h))


def reanclar_comandas(venta_reserva_id, fecha_vieja, hora_vieja,
                      fecha_nueva, hora_nueva):
    """Mueve el objetivo de las comandas pendientes ancladas al horario viejo
    del servicio al horario nuevo. Devuelve cuántas movió.

    Usa `.update()` a propósito: no pasa por Comanda.save() (que tiene lógica
    de inventario al cambiar de estado) — acá solo cambia una fecha.
    """
    from .models import Comanda

    viejo = objetivo_de(fecha_vieja, hora_vieja)
    nuevo = objetivo_de(fecha_nueva, hora_nueva)
    if viejo is None or nuevo is None or viejo == nuevo:
        return 0
    movidas = (Comanda.objects
               .filter(venta_reserva_id=venta_reserva_id,
                       estado__in=ESTADOS_QUE_SIGUEN,
                       fecha_entrega_objetivo=viejo)
               .update(fecha_entrega_objetivo=nuevo))
    if movidas:
        logger.info('Comandas re-ancladas: %s de la reserva #%s pasan de %s a %s',
                    movidas, venta_reserva_id, viejo, nuevo)
    return movidas
