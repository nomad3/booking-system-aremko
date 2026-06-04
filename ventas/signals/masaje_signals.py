"""Conexión-Masajes — signal que genera participantes al guardar un masaje.

Al guardar un ReservaServicio de masaje con cantidad_personas >= 1, se generan los
ParticipanteMasajeReserva (incluido el masaje individual: 1 persona → 1 ficha del
comprador). Defensivo: NUNCA rompe el guardado (si la tabla aún no existe —antes
del migrate en Render— o hay cualquier error, se traga y se loguea).
"""

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from ..models import ReservaServicio

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ReservaServicio, dispatch_uid='masaje_generar_participantes')
def generar_participantes_al_guardar_masaje(sender, instance, **kwargs):
    try:
        cantidad = getattr(instance, 'cantidad_personas', 0) or 0
        if cantidad < 1:
            return
        servicio = getattr(instance, 'servicio', None)
        if getattr(servicio, 'tipo_servicio', None) != 'masaje':
            return
        venta = getattr(instance, 'venta_reserva', None)
        if venta is None:
            return
        from ..services.masaje_participantes_service import generar_participantes_masaje
        generar_participantes_masaje(venta)
    except Exception as exc:  # nunca interrumpir el guardado de la reserva
        logger.warning("[Masajes] No se generaron participantes (no critico): %s", exc)
