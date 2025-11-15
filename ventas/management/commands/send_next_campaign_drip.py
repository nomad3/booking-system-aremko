# -*- coding: utf-8 -*-
"""
Management command para ejecutar el siguiente envío de la campaña drip
Uso: python manage.py send_next_campaign_drip
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.core.cache import cache
import logging
import time

from ventas.models import CommunicationLog, Contact, Company

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía el siguiente email de la campaña de prospección drip'

    def handle(self, *args, **options):
        """
        Busca y envía el siguiente email pendiente de la campaña drip
        """
        try:
            # Buscar el siguiente email pendiente en la cola
            next_email = CommunicationLog.objects.filter(
                status='PENDING',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).order_by('created_at').first()
            
            if not next_email:
                self.stdout.write("Sin pendientes.")
                return
            
            # Enviar el email
            success = self.send_email(next_email)
            
            if success:
                # Marcar como enviado
                next_email.mark_as_sent()
                
                # Actualizar progreso en cache
                self.update_progress_cache()
                
                self.stdout.write(f"Enviado a: {next_email.destination}")
                
                # Log para auditoría
                logger.info(f"Email enviado exitosamente a {next_email.destination}")
                
            else:
                # Marcar como fallido
                next_email.mark_as_failed()
                self.stdout.write(f"Error enviando a: {next_email.destination}")
                logger.error(f"Falló envío a {next_email.destination}")
                
        except Exception as e:
            self.stdout.write(f"Error en send_next_campaign_drip: {str(e)}")
            logger.error(f"Error en send_next_campaign_drip: {str(e)}")

    def send_email(self, communication_log):
        """
        Envía un email usando la información del CommunicationLog
        """
        try:
            # Verificar que tengamos las configuraciones necesarias
            if not settings.EMAIL_HOST_USER:
                logger.error("EMAIL_HOST_USER no configurado")
                return False
            
            # Crear el email
            email = EmailMultiAlternatives(
                subject=communication_log.subject,
                body=communication_log.content,  # Texto plano como fallback
                from_email=getattr(settings, 'VENTAS_FROM_EMAIL', settings.EMAIL_HOST_USER),
                to=[communication_log.destination]
            )
            
            # Agregar contenido HTML si existe
            html_content = communication_log.content
            if html_content:
                email.attach_alternative(html_content, "text/html")
            
            # Enviar
            email.send()
            
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email a {communication_log.destination}: {str(e)}")
            return False

    def update_progress_cache(self):
        """
        Actualiza el progreso de la campaña en cache
        """
        try:
            # Contar emails enviados y pendientes
            total_sent = CommunicationLog.objects.filter(
                status='SENT',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).count()
            
            total_pending = CommunicationLog.objects.filter(
                status='PENDING',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).count()
            
            total_failed = CommunicationLog.objects.filter(
                status='FAILED',
                communication_type='EMAIL',
                message_type='PROMOTIONAL'
            ).count()
            
            total_emails = total_sent + total_pending + total_failed
            
            progress_data = {
                'total': total_emails,
                'sent': total_sent,
                'pending': total_pending,
                'failed': total_failed,
                'percentage': round((total_sent / total_emails * 100), 2) if total_emails > 0 else 0,
                'last_updated': timezone.now().isoformat()
            }
            
            # Guardar en cache por 1 hora
            cache.set('campaign_progress', progress_data, 3600)
            
        except Exception as e:
            logger.error(f"Error actualizando progreso en cache: {str(e)}")