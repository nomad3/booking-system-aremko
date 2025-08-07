# -*- coding: utf-8 -*-
"""
Servicio de Comunicación Inteligente con Anti-Spam
Gestiona el envío de SMS y emails respetando límites y preferencias del cliente
"""

import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

from ..models import (
    Cliente, Campaign, CommunicationLimit, ClientPreferences, 
    CommunicationLog, SMSTemplate, VentaReserva
)
from .redvoiss_service import redvoiss_service

logger = logging.getLogger(__name__)


class CommunicationService:
    """
    Servicio principal para comunicación inteligente con clientes
    """
    
    def __init__(self):
        self.sms_service = redvoiss_service
    
    def send_booking_confirmation_sms(self, booking_id, cliente_id=None):
        """
        Envía SMS de confirmación de reserva
        """
        try:
            # Obtener reserva y cliente
            booking = VentaReserva.objects.get(id=booking_id)
            cliente = booking.cliente if not cliente_id else Cliente.objects.get(id=cliente_id)
            
            # Verificar si se puede enviar
            if not self._can_send_communication(cliente, 'SMS', 'BOOKING_CONFIRMATION'):
                return {'success': False, 'reason': 'blocked_by_limits_or_preferences'}
            
            # Obtener el primer servicio reservado
            from ..models import ReservaServicio
            reserva_servicio = ReservaServicio.objects.filter(venta_reserva=booking).first()
            
            if reserva_servicio:
                servicio_nombre = reserva_servicio.servicio.nombre
                fecha_str = reserva_servicio.fecha_agendamiento.strftime('%d/%m/%Y')
                hora_str = reserva_servicio.hora_inicio.strftime('%H:%M')
            else:
                servicio_nombre = 'tu servicio'
                fecha_str = booking.fecha_reserva.strftime('%d/%m/%Y')
                hora_str = booking.fecha_reserva.strftime('%H:%M')
            
            # Obtener plantilla
            template = SMSTemplate.objects.filter(
                message_type='BOOKING_CONFIRMATION',
                is_active=True
            ).first()
            
            if not template:
                message = f"✅ Reserva confirmada para {fecha_str} a las {hora_str}. ¡Te esperamos! - Aremko"
            else:
                message = template.render_message(
                    cliente,
                    servicio=servicio_nombre,
                    fecha=fecha_str,
                    hora=hora_str
                )
            
            # Enviar SMS
            result = self.sms_service.send_sms(
                destination=cliente.telefono,
                message=message,
                bulk_name=f"Confirmación Reserva {booking_id}"
            )
            
            if result['success']:
                # Registrar comunicación
                self._log_communication(
                    cliente=cliente,
                    communication_type='SMS',
                    message_type='BOOKING_CONFIRMATION',
                    content=message,
                    destination=cliente.telefono,
                    external_id=result['batch_id'],
                    booking_id=booking_id,
                    cost=12  # Costo por SMS según cotización
                )
                
                # Actualizar límites
                self._update_communication_limits(cliente, 'SMS')
                
                logger.info(f"SMS confirmación enviado a {cliente.nombre} para booking {booking_id}")
                return {'success': True, 'batch_id': result['batch_id']}
            else:
                logger.error(f"Error enviando SMS confirmación: {result['error']}")
                return {'success': False, 'error': result['error']}
                
        except Exception as e:
            logger.error(f"Error en send_booking_confirmation_sms: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_booking_reminder_sms(self, booking_id, hours_before=24):
        """
        Envía SMS recordatorio de cita
        """
        try:
            booking = VentaReserva.objects.get(id=booking_id)
            cliente = booking.cliente
            
            # Obtener el primer servicio reservado
            from ..models import ReservaServicio
            reserva_servicio = ReservaServicio.objects.filter(venta_reserva=booking).first()
            
            if reserva_servicio:
                # Verificar si es momento de enviar (X horas antes)
                booking_datetime = timezone.make_aware(
                    datetime.combine(reserva_servicio.fecha_agendamiento, reserva_servicio.hora_inicio)
                )
                servicio_nombre = reserva_servicio.servicio.nombre
                fecha_str = reserva_servicio.fecha_agendamiento.strftime('%d/%m/%Y')
                hora_str = reserva_servicio.hora_inicio.strftime('%H:%M')
            else:
                # Fallback a fecha de venta si no hay servicio específico
                booking_datetime = booking.fecha_reserva
                servicio_nombre = 'tu servicio'
                fecha_str = booking.fecha_reserva.strftime('%d/%m/%Y')
                hora_str = booking.fecha_reserva.strftime('%H:%M')
            
            reminder_time = booking_datetime - timedelta(hours=hours_before)
            
            if timezone.now() < reminder_time:
                return {'success': False, 'reason': 'too_early'}
            
            # Verificar límites y preferencias
            if not self._can_send_communication(cliente, 'SMS', 'BOOKING_REMINDER'):
                return {'success': False, 'reason': 'blocked_by_limits_or_preferences'}
            
            # Plantilla de recordatorio
            template = SMSTemplate.objects.filter(
                message_type='BOOKING_REMINDER',
                is_active=True
            ).first()
            
            if not template:
                message = f"🔔 Recordatorio: Tienes una cita mañana {fecha_str} a las {hora_str}. ¡No olvides! - Aremko"
            else:
                message = template.render_message(
                    cliente,
                    servicio=servicio_nombre,
                    fecha=fecha_str,
                    hora=hora_str
                )
            
            # Enviar SMS
            result = self.sms_service.send_sms(
                destination=cliente.telefono,
                message=message,
                bulk_name=f"Recordatorio {booking_id}"
            )
            
            if result['success']:
                self._log_communication(
                    cliente=cliente,
                    communication_type='SMS',
                    message_type='BOOKING_REMINDER',
                    content=message,
                    destination=cliente.telefono,
                    external_id=result['batch_id'],
                    booking_id=booking_id,
                    cost=12
                )
                
                self._update_communication_limits(cliente, 'SMS')
                
                logger.info(f"SMS recordatorio enviado a {cliente.nombre} para booking {booking_id}")
                return {'success': True, 'batch_id': result['batch_id']}
            else:
                return {'success': False, 'error': result['error']}
                
        except Exception as e:
            logger.error(f"Error en send_booking_reminder_sms: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_birthday_sms(self, cliente_id):
        """
        Envía SMS de felicitación de cumpleaños (máximo 1 por año)
        """
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            
            # Verificar límites especiales de cumpleaños
            limit, created = CommunicationLimit.objects.get_or_create(cliente=cliente)
            if not limit.can_send_birthday_sms():
                return {'success': False, 'reason': 'birthday_sms_already_sent_this_year'}
            
            # Verificar preferencias generales
            if not self._can_send_communication(cliente, 'SMS', 'BIRTHDAY'):
                return {'success': False, 'reason': 'blocked_by_preferences'}
            
            # Plantilla de cumpleaños
            template = SMSTemplate.objects.filter(
                message_type='BIRTHDAY',
                is_active=True
            ).first()
            
            if not template:
                message = f"🎉 ¡Feliz cumpleaños {cliente.nombre}! Esperamos que tengas un día maravilloso. ¡Te deseamos lo mejor! - Aremko"
            else:
                message = template.render_message(cliente)
            
            # Enviar SMS
            result = self.sms_service.send_sms(
                destination=cliente.telefono,
                message=message,
                bulk_name=f"Cumpleaños {cliente.nombre}"
            )
            
            if result['success']:
                self._log_communication(
                    cliente=cliente,
                    communication_type='SMS',
                    message_type='BIRTHDAY',
                    content=message,
                    destination=cliente.telefono,
                    external_id=result['batch_id'],
                    cost=12
                )
                
                # Registrar cumpleaños enviado
                limit.record_birthday_sms_sent()
                
                logger.info(f"SMS cumpleaños enviado a {cliente.nombre}")
                return {'success': True, 'batch_id': result['batch_id']}
            else:
                return {'success': False, 'error': result['error']}
                
        except Exception as e:
            logger.error(f"Error en send_birthday_sms: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_reactivation_email(self, cliente_id, campaign=None):
        """
        Envía email de reactivación para clientes inactivos (máximo 1 por trimestre)
        """
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            
            # Verificar límites de reactivación
            limit, created = CommunicationLimit.objects.get_or_create(cliente=cliente)
            if not limit.can_send_reactivation_email():
                return {'success': False, 'reason': 'reactivation_limit_reached'}
            
            # Verificar límites generales de email
            if not self._can_send_communication(cliente, 'EMAIL', 'REACTIVATION'):
                return {'success': False, 'reason': 'blocked_by_limits_or_preferences'}
            
            # Verificar que realmente esté inactivo (90+ días)
            if not self._is_client_inactive(cliente, days=90):
                return {'success': False, 'reason': 'client_not_inactive'}
            
            # Preparar email personalizado
            subject = f"Te extrañamos, {cliente.nombre} 💙"
            
            # Obtener último servicio para personalizar
            last_booking = VentaReserva.objects.filter(cliente=cliente).order_by('-fecha_reserva').first()
            last_service = last_booking.servicio.nombre if last_booking and hasattr(last_booking, 'servicio') else 'nuestros servicios'
            
            context = {
                'cliente': cliente,
                'last_service': last_service,
                'special_offer': '20% de descuento',  # Oferta especial para reactivación
                'company_name': 'Aremko'
            }
            
            # Renderizar template HTML
            html_content = render_to_string('emails/reactivation_email.html', context)
            
            # Enviar email
            success = send_mail(
                subject=subject,
                message='',  # Texto plano vacío, usamos HTML
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[cliente.email],
                html_message=html_content,
                fail_silently=False
            )
            
            if success:
                self._log_communication(
                    cliente=cliente,
                    communication_type='EMAIL',
                    message_type='REACTIVATION',
                    subject=subject,
                    content=html_content,
                    destination=cliente.email,
                    campaign=campaign
                )
                
                # Registrar email de reactivación enviado
                limit.record_reactivation_email_sent()
                
                logger.info(f"Email reactivación enviado a {cliente.nombre}")
                return {'success': True}
            else:
                return {'success': False, 'error': 'email_send_failed'}
                
        except Exception as e:
            logger.error(f"Error en send_reactivation_email: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_satisfaction_survey_sms(self, booking_id, hours_after=24):
        """
        Envía SMS con encuesta de satisfacción después del servicio
        """
        try:
            booking = VentaReserva.objects.get(id=booking_id)
            cliente = booking.cliente
            
            # Obtener el primer servicio reservado
            from ..models import ReservaServicio
            reserva_servicio = ReservaServicio.objects.filter(venta_reserva=booking).first()
            
            if reserva_servicio:
                # Verificar si ya pasó el tiempo necesario después del servicio
                booking_datetime = timezone.make_aware(
                    datetime.combine(reserva_servicio.fecha_agendamiento, reserva_servicio.hora_inicio)
                )
                servicio_nombre = reserva_servicio.servicio.nombre
            else:
                # Fallback a fecha de venta si no hay servicio específico
                booking_datetime = booking.fecha_reserva
                servicio_nombre = 'tu servicio'
            
            survey_time = booking_datetime + timedelta(hours=hours_after)
            
            if timezone.now() < survey_time:
                return {'success': False, 'reason': 'too_early'}
            
            # Verificar límites
            if not self._can_send_communication(cliente, 'SMS', 'SATISFACTION_SURVEY'):
                return {'success': False, 'reason': 'blocked_by_limits_or_preferences'}
            
            # Mensaje con link a encuesta
            survey_link = f"https://aremko-booking-system.onrender.com/encuesta/{booking_id}"
            message = f"¡Hola {cliente.nombre}! ¿Cómo fue tu experiencia con {servicio_nombre}? Tu opinión es muy importante: {survey_link} - Aremko"
            
            # Enviar SMS con respuesta habilitada
            result = self.sms_service.send_sms_with_reply(
                destination=cliente.telefono,
                message=message,
                bulk_name=f"Encuesta {booking_id}"
            )
            
            if result['success']:
                self._log_communication(
                    cliente=cliente,
                    communication_type='SMS',
                    message_type='SATISFACTION_SURVEY',
                    content=message,
                    destination=cliente.telefono,
                    external_id=result['batch_id'],
                    booking_id=booking_id,
                    cost=12
                )
                
                self._update_communication_limits(cliente, 'SMS')
                
                logger.info(f"SMS encuesta enviado a {cliente.nombre} para booking {booking_id}")
                return {'success': True, 'batch_id': result['batch_id']}
            else:
                return {'success': False, 'error': result['error']}
                
        except Exception as e:
            logger.error(f"Error en send_satisfaction_survey_sms: {str(e)}")
            return {'success': False, 'error': str(e)}
    
    def send_segmented_newsletter(self, segment_filter, subject, content, campaign=None):
        """
        Envía newsletter segmentado respetando límites de frecuencia
        """
        results = {'sent': 0, 'blocked': 0, 'errors': 0}
        
        try:
            # Obtener clientes del segmento
            clientes = Cliente.objects.filter(**segment_filter)
            
            for cliente in clientes:
                # Verificar límites de email semanal/mensual
                if not self._can_send_communication(cliente, 'EMAIL', 'NEWSLETTER'):
                    results['blocked'] += 1
                    continue
                
                # Verificar que tenga email
                if not cliente.email:
                    results['errors'] += 1
                    continue
                
                try:
                    # Personalizar contenido
                    personalized_content = content.replace('{nombre}', cliente.nombre)
                    
                    # Enviar email
                    success = send_mail(
                        subject=subject,
                        message=personalized_content,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[cliente.email],
                        fail_silently=False
                    )
                    
                    if success:
                        self._log_communication(
                            cliente=cliente,
                            communication_type='EMAIL',
                            message_type='NEWSLETTER',
                            subject=subject,
                            content=personalized_content,
                            destination=cliente.email,
                            campaign=campaign
                        )
                        
                        self._update_communication_limits(cliente, 'EMAIL')
                        results['sent'] += 1
                    else:
                        results['errors'] += 1
                        
                except Exception as e:
                    logger.error(f"Error enviando newsletter a {cliente.email}: {str(e)}")
                    results['errors'] += 1
            
            logger.info(f"Newsletter enviado: {results['sent']} enviados, {results['blocked']} bloqueados, {results['errors']} errores")
            return results
            
        except Exception as e:
            logger.error(f"Error en send_segmented_newsletter: {str(e)}")
            return results
    
    def _can_send_communication(self, cliente, communication_type, message_type):
        """
        Verifica si se puede enviar una comunicación según límites y preferencias
        """
        # Verificar preferencias del cliente
        preferences, created = ClientPreferences.objects.get_or_create(cliente=cliente)
        
        # Verificaciones generales
        if communication_type == 'SMS' and not preferences.accepts_sms:
            return False
        if communication_type == 'EMAIL' and not preferences.accepts_email:
            return False
        
        # Verificaciones específicas por tipo de mensaje
        message_type_checks = {
            'BOOKING_CONFIRMATION': preferences.accepts_booking_confirmations,
            'BOOKING_REMINDER': preferences.accepts_booking_reminders,
            'BIRTHDAY': preferences.accepts_birthday_messages,
            'PROMOTIONAL': preferences.accepts_promotional,
            'NEWSLETTER': preferences.accepts_newsletters,
            'REACTIVATION': preferences.accepts_reactivation,
        }
        
        if message_type in message_type_checks and not message_type_checks[message_type]:
            return False
        
        # Verificar horario preferido (solo para no-urgentes)
        non_urgent_types = ['NEWSLETTER', 'PROMOTIONAL', 'BIRTHDAY']
        if message_type in non_urgent_types and not preferences.can_contact_now():
            return False
        
        # Verificar límites de frecuencia
        limit, created = CommunicationLimit.objects.get_or_create(cliente=cliente)
        
        if communication_type == 'SMS' and not limit.can_send_sms():
            return False
        if communication_type == 'EMAIL' and not limit.can_send_email():
            return False
        
        return True
    
    def _is_client_inactive(self, cliente, days=90):
        """
        Verifica si un cliente está inactivo (sin reservas en X días)
        """
        cutoff_date = timezone.now().date() - timedelta(days=days)
        recent_bookings = VentaReserva.objects.filter(
            cliente=cliente,
            fecha_reserva__gte=cutoff_date
        ).exists()
        
        return not recent_bookings
    
    def _log_communication(self, cliente, communication_type, message_type, content, 
                          destination, subject='', external_id='', campaign=None, 
                          booking_id=None, cost=None):
        """
        Registra la comunicación en el log para auditoría
        """
        try:
            log = CommunicationLog.objects.create(
                cliente=cliente,
                campaign=campaign,
                communication_type=communication_type,
                message_type=message_type,
                subject=subject,
                content=content,
                destination=destination,
                external_id=external_id,
                booking_id=booking_id,
                cost=cost,
                triggered_by='communication_service'
            )
            log.mark_as_sent(external_id)
            
        except Exception as e:
            logger.error(f"Error registrando comunicación: {str(e)}")
    
    def _update_communication_limits(self, cliente, communication_type):
        """
        Actualiza los contadores de límites de comunicación
        """
        try:
            limit, created = CommunicationLimit.objects.get_or_create(cliente=cliente)
            
            if communication_type == 'SMS':
                limit.record_sms_sent()
            elif communication_type == 'EMAIL':
                limit.record_email_sent()
                
        except Exception as e:
            logger.error(f"Error actualizando límites: {str(e)}")
    
    def get_communication_stats(self, days=30):
        """
        Obtiene estadísticas de comunicación de los últimos X días
        """
        cutoff_date = timezone.now() - timedelta(days=days)
        
        logs = CommunicationLog.objects.filter(created_at__gte=cutoff_date)
        
        stats = {
            'total_sent': logs.filter(status='SENT').count(),
            'total_delivered': logs.filter(status='DELIVERED').count(),
            'total_failed': logs.filter(status='FAILED').count(),
            'total_blocked': logs.filter(status='BLOCKED').count(),
            'sms_sent': logs.filter(communication_type='SMS', status='SENT').count(),
            'emails_sent': logs.filter(communication_type='EMAIL', status='SENT').count(),
            'total_cost': sum(log.cost or 0 for log in logs if log.cost),
            'by_message_type': {},
        }
        
        # Estadísticas por tipo de mensaje
        for msg_type, _ in CommunicationLog.MESSAGE_TYPES:
            count = logs.filter(message_type=msg_type, status='SENT').count()
            if count > 0:
                stats['by_message_type'][msg_type] = count
        
        return stats


# Instancia global del servicio
communication_service = CommunicationService()