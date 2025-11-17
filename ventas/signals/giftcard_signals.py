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
    Envía email al comprador con los PDFs de las GiftCards

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

    # Preparar email
    cantidad_giftcards = len(giftcards)
    plural = "s" if cantidad_giftcards > 1 else ""

    subject = f"Tu{plural} GiftCard{plural} de Aremko Spa - Lista{plural} para Regalar"

    # Cuerpo del email
    destinatarios_nombres = ", ".join([gc.destinatario_nombre for gc in giftcards if gc.destinatario_nombre])

    body = f"""
¡Hola {comprador.nombre}!

¡Gracias por tu compra! Tu{plural} GiftCard{plural} de Aremko Aguas Calientes & Spa {"están" if plural else "está"} lista{plural}.

{'Has comprado' if plural else 'Has comprado'} {cantidad_giftcards} GiftCard{plural} para: {destinatarios_nombres}

DETALLES DE TU{'S' if plural else ''} GIFTCARD{plural.upper()}:

"""

    # Agregar detalles de cada GiftCard
    for i, giftcard in enumerate(giftcards, 1):
        body += f"""
{i}. GiftCard para: {giftcard.destinatario_nombre}
   Código: {giftcard.codigo}
   Valor: ${int(giftcard.monto_inicial):,}
   Válida hasta: {giftcard.fecha_vencimiento.strftime('%d/%m/%Y')}
   Email destinatario: {giftcard.destinatario_email or 'No especificado'}

"""

    body += f"""

CÓMO USAR LA{plural.upper()} GIFTCARD{plural.upper()}:

1. Reenvía este email (con el PDF adjunto) al destinatario
2. El destinatario debe contactar a Aremko por WhatsApp: +56 9 5790 2525
3. Mencionar el código de la GiftCard para reservar su experiencia

IMPORTANTE:
- Cada GiftCard es válida por 1 año desde la fecha de emisión
- Puede usarse una sola vez por el valor total
- El destinatario debe presentar el código al momento de reservar

UBICACIÓN:
Aremko Aguas Calientes & Spa
Puerto Varas, junto al Río Pescado

CONTACTO:
WhatsApp: +56 9 5790 2525
Email: spa@aremko.cl
Web: www.aremko.cl

¡Gracias por elegir Aremko Spa!
Un regalo que renueva cuerpo y alma en medio de la naturaleza.

---
Este email fue generado automáticamente.
Si tienes alguna consulta, contáctanos por WhatsApp.
"""

    # Crear email
    email = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[email_comprador],
        reply_to=['spa@aremko.cl']
    )

    # Adjuntar PDFs de las GiftCards
    for giftcard in giftcards:
        try:
            # Preparar datos para el PDF
            giftcard_data = {
                'codigo': giftcard.codigo,
                'experiencia_nombre': giftcard.servicio_asociado or 'Experiencia Aremko Spa',
                'destinatario_nombre': giftcard.destinatario_nombre,
                'mensaje_seleccionado': giftcard.mensaje_personalizado,
                'precio': int(giftcard.monto_inicial),
                'fecha_emision': giftcard.fecha_emision.strftime('%d/%m/%Y'),
                'fecha_vencimiento': giftcard.fecha_vencimiento.strftime('%d/%m/%Y'),
            }

            # Generar PDF
            pdf_content = GiftCardPDFService.generar_pdf_giftcard(giftcard_data)

            # Adjuntar al email
            filename = f"GiftCard_Aremko_{giftcard.codigo}.pdf"
            email.attach(filename, pdf_content, 'application/pdf')

            logger.info(f"PDF de GiftCard {giftcard.codigo} adjuntado al email")

        except Exception as e:
            logger.error(f"Error al generar PDF de GiftCard {giftcard.codigo}: {str(e)}", exc_info=True)

    # Enviar email
    try:
        email.send(fail_silently=False)
        logger.info(f"Email con {cantidad_giftcards} GiftCard{plural} enviado a {email_comprador}")

        # Marcar GiftCards como enviadas
        for giftcard in giftcards:
            giftcard.enviado_email = True
            giftcard.save()

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
