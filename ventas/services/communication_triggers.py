# -*- coding: utf-8 -*-
"""
Triggers automáticos para comunicación contextual
Maneja el envío automático de mensajes basado en eventos del sistema
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.cache import cache
import threading
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.conf import settings

from ..models import VentaReserva, Cliente, ReservaServicio, CommunicationLog
from .communication_service import communication_service

logger = logging.getLogger(__name__)


@receiver(post_save, sender=VentaReserva)
def handle_booking_confirmation(sender, instance, created, **kwargs):
    """
    Envía SMS de confirmación automáticamente cuando se crea una nueva reserva
    """
    if created and instance.cliente:
        try:
            logger.info(f"Enviando confirmación automática para reserva {instance.id}")
            # Si aún no existen servicios asociados, esperar a que se creen
            if not ReservaServicio.objects.filter(venta_reserva=instance).exists():
                logger.info(
                    f"Reserva {instance.id} creada sin servicios aún. Se enviará confirmación cuando se agregue el primer servicio."
                )
                return

            # Enviar confirmación inmediatamente (SMS + EMAIL)
            result = communication_service.send_booking_confirmation_dual(
                booking_id=instance.id,
                cliente_id=instance.cliente.id
            )
            
            if result['success']:
                channels = [ch for ch in result.get('channels_sent', []) if ch]
                channels_str = ' + '.join(channels)
                logger.info(f"✅ Confirmación automática enviada para reserva {instance.id} por {channels_str}")
                
                # Log específico por canal
                if result.get('sms_result', {}).get('success'):
                    logger.info(f"📱 SMS confirmación enviado para reserva {instance.id}")
                if result.get('email_result', {}).get('success'):
                    logger.info(f"📧 Email confirmación enviado para reserva {instance.id}")
            else:
                logger.warning(f"⚠️ No se pudo enviar confirmación para reserva {instance.id}: {result.get('reason', 'unknown')}")
                
        except Exception as e:
            logger.error(f"Error en trigger confirmación reserva: {str(e)}")


@receiver(post_save, sender=ReservaServicio)
def handle_service_added(sender, instance, created, **kwargs):
    """
    Cuando se agrega el primer ReservaServicio a una VentaReserva, enviar confirmación si no se envió.
    """
    if created and instance.venta_reserva and instance.venta_reserva.cliente:
        booking = instance.venta_reserva
        try:
            # Si ya se envió, no hacer nada
            already_sent = CommunicationLog.objects.filter(
                booking_id=booking.id,
                communication_type='EMAIL',
                message_type='BOOKING_CONFIRMATION',
                status__in=['SENT', 'PENDING']
            ).exists()
            if already_sent:
                return

            # Debounce: enviar 60s después del último servicio agregado
            cache_key = f"booking_confirm_debounce_{booking.id}"
            token = timezone.now().isoformat()
            cache.set(cache_key, token, timeout=300)

            def _send_if_stable():
                try:
                    current = cache.get(cache_key)
                    if current != token:
                        return  # llegó otro servicio, se reprograma con el nuevo token
                    # Re-chequear que existan servicios y que no se haya enviado aún
                    if not ReservaServicio.objects.filter(venta_reserva=booking).exists():
                        return
                    already = CommunicationLog.objects.filter(
                        booking_id=booking.id,
                        communication_type='EMAIL',
                        message_type='BOOKING_CONFIRMATION',
                        status__in=['SENT', 'PENDING']
                    ).exists()
                    if already:
                        return
                    logger.info(
                        f"Enviando confirmación consolidada (debounce) para reserva {booking.id}"
                    )
                    communication_service.send_booking_confirmation_dual(
                        booking_id=booking.id,
                        cliente_id=booking.cliente.id
                    )
                except Exception as ex:
                    logger.error(f"Error en debounce confirmación reserva {booking.id}: {ex}")

            threading.Timer(60.0, _send_if_stable).start()
        except Exception as e:
            logger.error(f"Error en handle_service_added: {str(e)}")


def schedule_booking_reminders():
    """
    Función que debe ejecutarse periódicamente (cada hora) para enviar recordatorios
    Busca reservas que necesitan recordatorio (24h antes)
    """
    try:
        # Buscar reservas para mañana (24h de diferencia aprox)
        tomorrow = timezone.now().date() + timedelta(days=1)
        
        # Obtener reservas de mañana que aún no han recibido recordatorio
        reservas_mañana = VentaReserva.objects.filter(
            fecha_reserva=tomorrow
        ).exclude(
            # Excluir las que ya tienen un log de recordatorio
            cliente__communication_logs__message_type='BOOKING_REMINDER',
            cliente__communication_logs__booking_id=models.F('id'),
            cliente__communication_logs__status='SENT'
        )
        
        logger.info(f"Procesando {reservas_mañana.count()} recordatorios de reserva")
        
        for reserva in reservas_mañana:
            try:
                result = communication_service.send_booking_reminder_sms(
                    booking_id=reserva.id,
                    hours_before=24
                )
                
                if result['success']:
                    logger.info(f"Recordatorio enviado para reserva {reserva.id}")
                else:
                    logger.debug(f"Recordatorio no enviado para reserva {reserva.id}: {result.get('reason', 'unknown')}")
                    
            except Exception as e:
                logger.error(f"Error enviando recordatorio para reserva {reserva.id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error en schedule_booking_reminders: {str(e)}")


def schedule_satisfaction_surveys():
    """
    Función que debe ejecutarse periódicamente para enviar encuestas de satisfacción
    Busca reservas que terminaron hace 24h y aún no tienen encuesta
    """
    try:
        # Buscar reservas que terminaron ayer (24h después del servicio)
        yesterday = timezone.now().date() - timedelta(days=1)
        
        # Obtener reservas de ayer que no han recibido encuesta
        reservas_ayer = VentaReserva.objects.filter(
            fecha_reserva=yesterday
        ).exclude(
            cliente__communication_logs__message_type='SATISFACTION_SURVEY',
            cliente__communication_logs__booking_id=models.F('id'),
            cliente__communication_logs__status='SENT'
        )
        
        logger.info(f"Procesando {reservas_ayer.count()} encuestas de satisfacción")
        
        for reserva in reservas_ayer:
            try:
                result = communication_service.send_satisfaction_survey_sms(
                    booking_id=reserva.id,
                    hours_after=24
                )
                
                if result['success']:
                    logger.info(f"Encuesta enviada para reserva {reserva.id}")
                else:
                    logger.debug(f"Encuesta no enviada para reserva {reserva.id}: {result.get('reason', 'unknown')}")
                    
            except Exception as e:
                logger.error(f"Error enviando encuesta para reserva {reserva.id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error en schedule_satisfaction_surveys: {str(e)}")


def schedule_birthday_messages():
    """
    Función que debe ejecutarse diariamente para enviar mensajes de cumpleaños
    Nota: Requiere que el modelo Cliente tenga campo fecha_nacimiento
    """
    try:
        today = timezone.now().date()
        
        # Buscar clientes que cumplen años hoy
        # Nota: Esto requiere agregar campo fecha_nacimiento al modelo Cliente
        clientes_cumpleaños = Cliente.objects.filter(
            fecha_nacimiento__month=today.month,
            fecha_nacimiento__day=today.day
        )
        
        logger.info(f"Procesando {clientes_cumpleaños.count()} mensajes de cumpleaños")
        
        for cliente in clientes_cumpleaños:
            try:
                result = communication_service.send_birthday_sms(cliente.id)
                
                if result['success']:
                    logger.info(f"SMS cumpleaños enviado a {cliente.nombre}")
                else:
                    logger.debug(f"SMS cumpleaños no enviado a {cliente.nombre}: {result.get('reason', 'unknown')}")
                    
            except Exception as e:
                logger.error(f"Error enviando cumpleaños a cliente {cliente.id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error en schedule_birthday_messages: {str(e)}")


def schedule_reactivation_campaigns():
    """
    Función que debe ejecutarse semanalmente para identificar y reactivar clientes inactivos
    """
    try:
        from django.db.models import Q, Max
        
        # Buscar clientes inactivos (sin reservas en 90+ días)
        inactive_cutoff = timezone.now().date() - timedelta(days=90)
        
        # Clientes con última reserva hace más de 90 días
        inactive_clients = Cliente.objects.annotate(
            last_booking_date=Max('ventareserva__fecha_reserva')
        ).filter(
            Q(last_booking_date__lt=inactive_cutoff) | Q(last_booking_date__isnull=True)
        ).exclude(
            # Excluir los que ya recibieron email de reactivación este trimestre
            communication_logs__message_type='REACTIVATION',
            communication_logs__created_at__gte=timezone.now() - timedelta(days=90)
        )
        
        logger.info(f"Procesando {inactive_clients.count()} clientes para reactivación")
        
        for cliente in inactive_clients[:50]:  # Limitar a 50 por ejecución para no saturar
            try:
                # Verificar que tenga email
                if not cliente.email:
                    continue
                
                result = communication_service.send_reactivation_email(cliente.id)
                
                if result['success']:
                    logger.info(f"Email reactivación enviado a {cliente.nombre}")
                else:
                    logger.debug(f"Email reactivación no enviado a {cliente.nombre}: {result.get('reason', 'unknown')}")
                    
            except Exception as e:
                logger.error(f"Error enviando reactivación a cliente {cliente.id}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error en schedule_reactivation_campaigns: {str(e)}")


def schedule_vip_newsletters():
    """
    Función que debe ejecutarse mensualmente para enviar newsletter a clientes VIP
    """
    try:
        from django.db.models import Count, Sum
        
        # Criterios para clientes VIP (6+ visitas y alto gasto)
        VISIT_THRESHOLD_VIP = 6
        SPEND_THRESHOLD_HIGH = 150000  # CLP
        
        # Obtener clientes VIP
        vip_clients = Cliente.objects.annotate(
            num_visits=Count('ventareserva'),
            total_spend=Sum('ventareserva__total')
        ).filter(
            num_visits__gte=VISIT_THRESHOLD_VIP,
            total_spend__gte=SPEND_THRESHOLD_HIGH,
            email__isnull=False
        ).exclude(
            # Excluir los que ya recibieron newsletter este mes
            communication_logs__message_type='NEWSLETTER',
            communication_logs__created_at__gte=timezone.now().replace(day=1)
        )
        
        if vip_clients.exists():
            # Contenido del newsletter VIP
            subject = f"🌟 Newsletter Exclusivo VIP - {timezone.now().strftime('%B %Y')}"
            content = """
            ¡Hola {nombre}!
            
            Como miembro VIP de Aremko, queremos compartir contigo nuestras novedades exclusivas:
            
            🎯 Nuevos tratamientos premium disponibles solo para clientes VIP
            📅 Acceso prioritario a reservas en horarios premium
            💎 Descuentos especiales del 15% en paquetes de servicios
            🎁 Regalo sorpresa en tu próxima visita
            
            Tu fidelidad es muy valiosa para nosotros. ¡Gracias por elegir Aremko!
            
            Reserva tu próxima cita: https://aremko-booking-system.onrender.com
            
            Con cariño,
            El equipo de Aremko
            """
            
            # Enviar newsletter segmentado
            result = communication_service.send_segmented_newsletter(
                segment_filter={
                    'id__in': [client.id for client in vip_clients]
                },
                subject=subject,
                content=content
            )
            
            logger.info(f"Newsletter VIP enviado: {result['sent']} exitosos, {result['blocked']} bloqueados")
        
    except Exception as e:
        logger.error(f"Error en schedule_vip_newsletters: {str(e)}")


# Funciones auxiliares para configurar tareas periódicas

def setup_communication_schedules():
    """
    Configura las tareas periódicas de comunicación
    Esta función debe ser llamada desde el management command o configuración de Celery
    """
    schedules = {
        'booking_reminders': {
            'function': schedule_booking_reminders,
            'interval': 'hourly',
            'description': 'Envío de recordatorios de cita (cada hora)'
        },
        'satisfaction_surveys': {
            'function': schedule_satisfaction_surveys,
            'interval': 'daily',
            'description': 'Envío de encuestas de satisfacción (diario)'
        },
        'birthday_messages': {
            'function': schedule_birthday_messages,
            'interval': 'daily',
            'description': 'Envío de mensajes de cumpleaños (diario)'
        },
        'reactivation_campaigns': {
            'function': schedule_reactivation_campaigns,
            'interval': 'weekly',
            'description': 'Envío de campañas de reactivación (semanal)'
        },
        'vip_newsletters': {
            'function': schedule_vip_newsletters,
            'interval': 'monthly',
            'description': 'Envío de newsletter VIP (mensual)'
        }
    }
    
    return schedules


# Management command helper functions

def test_communication_system():
    """
    Función de prueba para validar que todo el sistema de comunicación funciona
    """
    try:
        logger.info("=== INICIANDO PRUEBA DEL SISTEMA DE COMUNICACIÓN ===")
        
        # 1. Probar conexión con Redvoiss
        from .redvoiss_service import redvoiss_service
        
        logger.info("1. Probando conexión con Redvoiss...")
        connection_test = redvoiss_service.greet()
        
        if connection_test['success']:
            logger.info(f"✅ Conexión exitosa: {connection_test['message']}")
        else:
            logger.error(f"❌ Error de conexión: {connection_test['message']}")
            return False
        
        # 2. Obtener estadísticas
        logger.info("2. Obteniendo estadísticas de comunicación...")
        stats = communication_service.get_communication_stats(days=7)
        logger.info(f"📊 Estadísticas (últimos 7 días): {stats}")
        
        # 3. Verificar modelos
        logger.info("3. Verificando modelos de base de datos...")
        from ..models import CommunicationLimit, ClientPreferences, CommunicationLog
        
        limits_count = CommunicationLimit.objects.count()
        preferences_count = ClientPreferences.objects.count()
        logs_count = CommunicationLog.objects.count()
        
        logger.info(f"📋 Límites: {limits_count}, Preferencias: {preferences_count}, Logs: {logs_count}")
        
        logger.info("=== PRUEBA COMPLETADA EXITOSAMENTE ===")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error en prueba del sistema: {str(e)}")
        return False