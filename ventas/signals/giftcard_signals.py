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


# El mapeo de experiencia (nombre/descripción/foto) vive ahora en
# GiftCardPDFService.datos_carta() — fuente única para carta, email y descarga.
# Antes acá había un dict hardcodeado con IDs viejos ('tinas', 'masajes'...) que
# no conocía las experiencias insignia → la carta salía "Experiencia Aremko Spa".


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

    # Datos de la carta desde la fuente única (nombre/descripción/foto reales de
    # la experiencia en BD, con fallback legado para giftcards antiguas).
    giftcards_data = [GiftCardPDFService.datos_carta(gc) for gc in giftcards]

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

    # OPTIMIZACIÓN: Solo recalcular en creación, no en cada actualización
    # Esto evita recálculos innecesarios cuando se edita la GiftCard en admin
    if not created:
        logger.debug(f"Saltando recálculo para GiftCard {instance.codigo} (actualización, no creación)")
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


# --- Signal de Protección Preventiva para Saldos de GiftCards ---

@receiver(post_save, sender=Pago)
def verificar_saldo_giftcard_post_pago(sender, instance, created, **kwargs):
    """
    PROTECCIÓN PREVENTIVA: Verifica y corrige automáticamente el saldo de GiftCards
    después de cada pago.

    OPTIMIZACIÓN: Solo se ejecuta cuando se CREA un nuevo pago (not en updates)
    para evitar queries innecesarias que ralentizan el sistema.

    Este signal previene el problema de saldos incorrectos que ocurrió cuando
    los pagos fueron creados con bulk_create(), update(), o desde el admin sin
    ejecutar el método save() del modelo Pago.
    """
    # OPTIMIZACIÓN 1: Solo ejecutar en creación, no en actualización
    if not created:
        return

    # Solo procesar pagos con GiftCard
    if instance.metodo_pago != 'giftcard' or not instance.giftcard:
        return

    try:
        from django.db.models import Sum
        from decimal import Decimal

        gc = instance.giftcard

        # OPTIMIZACIÓN 2: Calcular saldo de forma más eficiente
        # En lugar de sumar TODOS los pagos, restamos directamente el monto del pago actual
        saldo_esperado = gc.monto_disponible - instance.monto

        # OPTIMIZACIÓN 3: Solo hacer la query Sum() si hay inconsistencia
        # La mayoría de las veces el saldo ya estará correcto
        if gc.monto_disponible != saldo_esperado:
            # Ahora sí, verificar con Sum() por seguridad
            total_usado = Pago.objects.filter(
                giftcard=gc,
                metodo_pago='giftcard'
            ).aggregate(total=Sum('monto'))['total'] or Decimal('0')

            saldo_esperado = gc.monto_inicial - total_usado

            logger.warning(
                f"🔧 PROTECCIÓN: Inconsistencia detectada en GiftCard {gc.codigo}. "
                f"Saldo actual: ${gc.monto_disponible}, Saldo esperado: ${saldo_esperado}. "
                f"Corrigiendo automáticamente..."
            )

            # Determinar estado correcto
            nuevo_estado = 'cobrado' if saldo_esperado == 0 else 'por_cobrar'

            # Actualizar saldo y estado
            # Usamos update() para evitar llamadas recursivas al signal
            GiftCard.objects.filter(pk=gc.pk).update(
                monto_disponible=saldo_esperado,
                estado=nuevo_estado
            )

            logger.info(
                f"✓ PROTECCIÓN: GiftCard {gc.codigo} corregida automáticamente. "
                f"Nuevo saldo: ${saldo_esperado}, Nuevo estado: {nuevo_estado}"
            )

    except Exception as e:
        logger.error(
            f"❌ PROTECCIÓN: Error al verificar saldo de GiftCard para Pago ID={instance.id}: {str(e)}",
            exc_info=True
        )
        # No re-lanzar la excepción para no interrumpir el proceso de guardado
        pass
