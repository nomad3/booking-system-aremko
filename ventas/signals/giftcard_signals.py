# -*- coding: utf-8 -*-
"""
Signals para gestión automática de GiftCards

Funcionalidad:
- Detecta cuando se registra un pago en una VentaReserva
- Si la venta tiene GiftCards asociadas, las procesa:
  1. Cambia estado de 'por_cobrar' → 'cobrado'
  2. Genera PDF de cada GiftCard
  3. Envía email al comprador con las GiftCards

Trigger: post_save en modelo Pago
"""

from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.mail import EmailMessage
from django.conf import settings
from ..models import Pago, GiftCard
from ..services.giftcard_pdf_service import GiftCardPDFService
import logging

logger = logging.getLogger(__name__)


def obtener_descripcion_experiencia(servicio_asociado):
    """
    Mapea el ID del servicio asociado con su descripción completa para GiftCards

    Args:
        servicio_asociado (str): ID del servicio (ej: 'tinas', 'masajes', etc.)

    Returns:
        str: Descripción completa de la experiencia
    """
    experiencias = {
        'tinas': 'Tinas calientes para dos personas en tinas con o sin hidromasaje junto al Río Pescado',
        'masajes': 'Masajes para dos en domos de Bienestar en medio del antiguo bosque nativo de Aremko, junto al Río Pescado',
        'cabanas': 'Alojamiento para dos en cabaña de maderas nativas, en medio del antiguo bosque nativo, junto al Río Pescado',
        'alojamiento_tinas': 'Alojamiento para dos en cabaña de maderas nativas + tinas calientes con o sin hidromasaje, en medio del antiguo bosque nativo junto al Río Pescado',
        'celebracion': 'Alojamiento para dos en cabaña de maderas nativas + tinas calientes con ambientación romántica (velas y botella de espumante) + desayuno, en medio del antiguo bosque nativo junto al Río Pescado',
        'monto_libre': 'Vale por el monto indicado para usar en cualquier experiencia de Aremko Spa'
    }

    return experiencias.get(servicio_asociado, 'Experiencia Aremko Spa')


@receiver(post_save, sender=Pago)
def enviar_giftcards_al_registrar_pago(sender, instance, created, **kwargs):
    """
    Signal que se ejecuta cuando se crea o actualiza un Pago

    Si la VentaReserva asociada tiene GiftCards pendientes, las procesa y envía por email
    """

    # Solo procesar cuando se CREA un nuevo pago (no al actualizar)
    if not created:
        return

    # Obtener la venta asociada al pago
    venta_reserva = instance.venta_reserva

    # Verificar si esta venta tiene GiftCards asociadas
    giftcards_pendientes = venta_reserva.giftcards.filter(estado='por_cobrar')

    if not giftcards_pendientes.exists():
        logger.info(f"VentaReserva #{venta_reserva.id} no tiene GiftCards pendientes")
        return

    logger.info(f"Procesando {giftcards_pendientes.count()} GiftCards de VentaReserva #{venta_reserva.id}")

    # Verificar si el pago cubre el total (o al menos una parte significativa)
    # Si la venta está totalmente pagada, enviar las GiftCards
    venta_reserva.calcular_total()  # Recalcular por si acaso

    if venta_reserva.estado_pago in ['pagado', 'parcial']:
        try:
            # Cambiar estado de las GiftCards
            for giftcard in giftcards_pendientes:
                giftcard.estado = 'cobrado'
                giftcard.save()
                logger.info(f"GiftCard {giftcard.codigo} cambiada a estado 'cobrado'")

            # Enviar email con las GiftCards
            enviar_email_giftcards(venta_reserva, list(giftcards_pendientes))

        except Exception as e:
            logger.error(f"Error al procesar GiftCards de VentaReserva #{venta_reserva.id}: {str(e)}", exc_info=True)


def enviar_email_giftcards(venta_reserva, giftcards):
    """
    Envía email al comprador con las GiftCards en formato HTML

    Args:
        venta_reserva: VentaReserva instance
        giftcards: Lista de GiftCard instances
    """

    # Obtener email del comprador
    comprador = venta_reserva.cliente
    email_comprador = comprador.email

    # Si el comprador no tiene email, intentar usar el de la primera GiftCard
    if not email_comprador:
        email_comprador = giftcards[0].comprador_email if giftcards else None

    if not email_comprador:
        logger.error(f"No se puede enviar GiftCards: comprador de VentaReserva #{venta_reserva.id} no tiene email")
        return

    # Preparar datos de las GiftCards para el servicio
    giftcards_data = []
    for giftcard in giftcards:
        giftcard_data = {
            'codigo': giftcard.codigo,
            'experiencia_nombre': obtener_descripcion_experiencia(giftcard.servicio_asociado),
            'destinatario_nombre': giftcard.destinatario_nombre,
            'mensaje_seleccionado': giftcard.mensaje_personalizado or 'Un regalo especial para ti',
            'precio': int(giftcard.monto_inicial),
            'fecha_emision': giftcard.fecha_emision,
            'fecha_vencimiento': giftcard.fecha_vencimiento,
        }
        giftcards_data.append(giftcard_data)

    # Usar el servicio de GiftCardPDFService para enviar el email con HTML
    try:
        resultado = GiftCardPDFService.enviar_giftcard_por_email(
            comprador_email=email_comprador,
            comprador_nombre=comprador.nombre,
            giftcards_data=giftcards_data
        )

        if resultado:
            logger.info(f"Email HTML con {len(giftcards)} GiftCard(s) enviado a {email_comprador}")

            # Marcar GiftCards como enviadas
            for giftcard in giftcards:
                giftcard.enviado_email = True
                giftcard.save()
        else:
            logger.error(f"Falló el envío de email a {email_comprador}")

    except Exception as e:
        logger.error(f"Error al enviar email con GiftCards a {email_comprador}: {str(e)}", exc_info=True)


# --- Signals para Recalcular Total de VentaReserva ---

@receiver(post_save, sender=GiftCard)
def recalcular_total_al_crear_giftcard(sender, instance, created, raw, **kwargs):
    """
    Recalcula el total de la VentaReserva cuando se crea o actualiza una GiftCard

    Similar a los signals de ReservaServicio y ReservaProducto
    """
    # Skip if fixture loading
    if raw:
        return

    try:
        if instance.venta_reserva:
            logger.info(f"Recalculando total de VentaReserva #{instance.venta_reserva.id} por GiftCard {instance.codigo}")
            instance.venta_reserva.calcular_total()
    except Exception as e:
        logger.error(f"Error recalculando total después de guardar GiftCard {instance.codigo}: {e}", exc_info=True)


@receiver(post_delete, sender=GiftCard)
def recalcular_total_al_eliminar_giftcard(sender, instance, **kwargs):
    """
    Recalcula el total de la VentaReserva cuando se elimina una GiftCard
    """
    try:
        if instance.venta_reserva:
            logger.info(f"Recalculando total de VentaReserva #{instance.venta_reserva.id} tras eliminar GiftCard {instance.codigo}")
            instance.venta_reserva.calcular_total()
    except Exception as e:
        logger.error(f"Error recalculando total después de eliminar GiftCard {instance.codigo}: {e}", exc_info=True)
