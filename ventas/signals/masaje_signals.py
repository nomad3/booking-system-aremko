"""Conexión-Masajes — signal que genera participantes al guardar un masaje.

Al guardar un ReservaServicio de masaje con cantidad_personas >= 1, se generan los
ParticipanteMasajeReserva (incluido el masaje individual: 1 persona → 1 ficha del
comprador). Defensivo: NUNCA rompe el guardado (si la tabla aún no existe —antes
del migrate en Render— o hay cualquier error, se traga y se loguea).
"""

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from ..models import ReservaServicio, BienestarMasajeFicha

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


@receiver(post_delete, sender=ReservaServicio, dispatch_uid='masaje_limpiar_participantes')
def limpiar_participantes_al_eliminar_masaje(sender, instance, **kwargs):
    """Al eliminar una línea de masaje, quita los participantes que sobren (sin
    ficha completada). Defensivo: nunca rompe la eliminación."""
    try:
        servicio = getattr(instance, 'servicio', None)
        if getattr(servicio, 'tipo_servicio', None) != 'masaje':
            return
        venta = getattr(instance, 'venta_reserva', None)
        if venta is None or not getattr(venta, 'pk', None):
            return  # si se borró toda la reserva, los participantes caen por cascade
        from ..services.masaje_participantes_service import sincronizar_participantes_masaje
        sincronizar_participantes_masaje(venta)
    except Exception as exc:
        logger.warning("[Masajes] No se limpiaron participantes (no critico): %s", exc)


@receiver(post_save, sender=BienestarMasajeFicha, dispatch_uid='masaje_programar_resumen')
def programar_resumen_al_completar_terapeuta(sender, instance, **kwargs):
    """Cuando la masajista completa su resumen en la ficha, programa el email de
    'resumen de bienestar' (F7). Defensivo + idempotente (no reenvía)."""
    try:
        from ..services.masaje_seguimiento_service import programar_resumen_bienestar
        programar_resumen_bienestar(instance)
    except Exception as exc:  # nunca interrumpir el guardado de la ficha
        logger.warning("[Masajes] No se programó el resumen de bienestar (no critico): %s", exc)
