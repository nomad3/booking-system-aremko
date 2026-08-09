# -*- coding: utf-8 -*-
"""Deshacer automático: si la línea de la artesanía se elimina de la reserva,
la pieza vuelve sola a disponible (pedido de Jorge 2026-08-09: «alguien puede
olvidar el procedimiento»). pre_delete a propósito: en post_delete el SET_NULL
ya habría cortado el enlace y no sabríamos qué pieza era."""
import logging
from datetime import date

from django.db.models.signals import pre_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_delete, sender='ventas.ReservaProducto',
          dispatch_uid='artesania_deshacer_venta_al_borrar_linea')
def deshacer_venta_al_borrar_linea(sender, instance, **kwargs):
    try:
        pieza = instance.artesania_pieza
    except Exception:
        return
    if pieza is None:
        return
    try:
        reserva_id = instance.venta_reserva_id
        pieza.estado = 'disponible'
        pieza.venta_linea = None
        pieza.venta_reserva = None
        pieza.venta_monto = None
        pieza.venta_fecha = None
        pieza.venta_forma_pago = ''
        pieza.notas = (f'{pieza.notas} · venta a reserva #{reserva_id} '
                       f'deshecha el {date.today():%d-%m-%Y}').strip(' ·')[:255]
        pieza.save()
        logger.info('Artesanía %s devuelta a disponible (línea eliminada de '
                    'la reserva #%s)', pieza.codigo, reserva_id)
    except Exception:
        logger.exception('No se pudo deshacer la venta de la pieza al borrar '
                         'la línea %s', instance.pk)
