# -*- coding: utf-8 -*-
"""
Comando para enviar campañas de email de forma controlada y segura
"""

import time
import logging
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.db import transaction

from ventas.models import EmailCampaign, EmailRecipient, EmailDeliveryLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía campañas de email de forma controlada respetando horarios y límites'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-id',
            type=int,
            help='ID específico de campaña a enviar'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=5,
            help='Número de emails por lote (default: 5)'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=6,
            help='Intervalo en minutos entre lotes (default: 6)'
        )
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Modo automático: procesar todas las campañas listas'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular envío sin enviar emails reales'
        )
        parser.add_argument(
            '--ignore-schedule',
            action='store_true',
            help='Ignorar restricciones de horario'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🚀 INICIANDO ENVÍO DE CAMPAÑAS EMAIL'))
        
        batch_size = options['batch_size']
        interval_minutes = options['interval']
        dry_run = options['dry_run']
        ignore_schedule = options['ignore_schedule']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️ MODO DRY-RUN: No se enviarán emails reales'))
        
        # Para modo auto, verificar horario general
        if options['auto'] and not ignore_schedule and not self.is_sending_time():
            self.stdout.write(self.style.WARNING('⏰ Fuera del horario de envío general. Saliendo.'))
            self.stdout.write('💡 Use --ignore-schedule para enviar fuera del horario')
            return
        
        if options['auto']:
            # Modo automático: procesar todas las campañas listas
            campaigns = EmailCampaign.objects.filter(status='ready')
            self.stdout.write(f'📊 Encontradas {campaigns.count()} campañas listas para envío')
            
            for campaign in campaigns:
                self.process_campaign(campaign, batch_size, interval_minutes, dry_run, ignore_schedule)
        
        elif options['campaign_id']:
            # Modo manual: procesar campaña específica
            try:
                campaign = EmailCampaign.objects.get(id=options['campaign_id'])
                if campaign.status != 'ready':
                    raise CommandError(f'❌ Campaña {campaign.id} no está lista para envío (estado: {campaign.status})')
                
                self.process_campaign(campaign, batch_size, interval_minutes, dry_run, ignore_schedule)
                
            except EmailCampaign.DoesNotExist:
                raise CommandError(f'❌ Campaña con ID {options["campaign_id"]} no encontrada')
        else:
            raise CommandError('❌ Debe especificar --campaign-id o --auto')

    def is_sending_time(self, campaign=None):
        """Verifica si estamos en horario de envío según configuración de campaña"""
        now = timezone.now()
        chile_time = now.astimezone(timezone.get_fixed_timezone(-180))  # UTC-3
        current_time = chile_time.time()
        
        # Horarios por defecto si no hay campaña específica
        start_time = "08:00"
        end_time = "21:00"
        
        # Usar horarios de la campaña si están configurados
        if campaign and campaign.schedule_config:
            start_time = campaign.schedule_config.get('start_time', start_time)
            end_time = campaign.schedule_config.get('end_time', end_time)
        
        # Convertir strings a time objects
        from datetime import time
        try:
            start_hour, start_min = map(int, start_time.split(':'))
            end_hour, end_min = map(int, end_time.split(':'))
            start_time_obj = time(start_hour, start_min)
            end_time_obj = time(end_hour, end_min)
            
            return start_time_obj <= current_time <= end_time_obj
        except (ValueError, AttributeError):
            # Fallback a horarios por defecto si hay error
            return 8 <= chile_time.hour <= 21

    def process_campaign(self, campaign, batch_size, interval_minutes, dry_run, ignore_schedule=False):
        """Procesa una campaña específica"""
        self.stdout.write(f'\n📧 Procesando campaña: {campaign.name}')
        
        # Usar configuración de la campaña si está disponible
        if campaign.schedule_config:
            campaign_batch_size = campaign.schedule_config.get('batch_size', batch_size)
            campaign_interval = campaign.schedule_config.get('interval_minutes', interval_minutes)
            self.stdout.write(f'📊 Usando configuración de campaña: {campaign_batch_size} emails cada {campaign_interval} minutos')
        else:
            campaign_batch_size = batch_size
            campaign_interval = interval_minutes
            self.stdout.write(f'📊 Usando configuración por defecto: {campaign_batch_size} emails cada {campaign_interval} minutos')
        
        # Verificar horario específico de la campaña
        if not ignore_schedule and not self.is_sending_time(campaign):
            start_time = campaign.schedule_config.get('start_time', '08:00') if campaign.schedule_config else '08:00'
            end_time = campaign.schedule_config.get('end_time', '21:00') if campaign.schedule_config else '21:00'
            self.stdout.write(self.style.WARNING(f'⏰ Campaña fuera de horario ({start_time}-{end_time}). Saltando.'))
            return
        
        # Obtener destinatarios pendientes
        pending_recipients = EmailRecipient.objects.filter(
            campaign=campaign,
            send_enabled=True,
            status='pending'
        ).order_by('priority', 'id')
        
        total_pending = pending_recipients.count()
        if total_pending == 0:
            self.stdout.write(self.style.WARNING(f'⚠️ No hay destinatarios pendientes para campaña {campaign.id}'))
            return
        
        self.stdout.write(f'📊 Destinatarios pendientes: {total_pending}')
        
        # Cambiar estado de campaña a 'sending'
        if not dry_run:
            campaign.status = 'sending'
            campaign.save()
        
        # Procesar en lotes
        processed = 0
        for i in range(0, total_pending, campaign_batch_size):
            batch = pending_recipients[i:i + campaign_batch_size]
            
            self.stdout.write(f'\n📤 Enviando lote {i//campaign_batch_size + 1}: {len(batch)} emails')
            
            for recipient in batch:
                try:
                    if self.send_email(recipient, dry_run):
                        processed += 1
                        if not dry_run:
                            recipient.mark_as_sent()
                    
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'❌ Error enviando a {recipient.email}: {e}'))
                    if not dry_run:
                        recipient.status = 'failed'
                        recipient.error_message = str(e)
                        recipient.save()
            
            # Pausa entre lotes (excepto el último)
            if i + campaign_batch_size < total_pending:
                self.stdout.write(f'⏸️ Pausa de {campaign_interval} minutos...')
                if not dry_run:
                    time.sleep(campaign_interval * 60)
        
        # Actualizar estado final de la campaña
        if not dry_run:
            remaining = EmailRecipient.objects.filter(
                campaign=campaign,
                send_enabled=True,
                status='pending'
            ).count()
            
            if remaining == 0:
                campaign.status = 'completed'
                campaign.save()
                self.stdout.write(self.style.SUCCESS(f'✅ Campaña {campaign.name} completada'))
            else:
                self.stdout.write(f'📊 Quedan {remaining} destinatarios pendientes')
        
        self.stdout.write(self.style.SUCCESS(f'✅ Procesados {processed} emails de la campaña {campaign.name}'))

    def send_email(self, recipient, dry_run=False):
        """Envía un email individual"""
        if dry_run:
            self.stdout.write(f'📧 [DRY-RUN] {recipient.email}: {recipient.personalized_subject[:50]}...')
            return True
        
        try:
            # Crear email
            msg = EmailMultiAlternatives(
                subject=recipient.personalized_subject,
                body=recipient.personalized_body,  # Fallback text
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[recipient.email]
            )
            
            # Agregar contenido HTML
            msg.attach_alternative(recipient.personalized_body, "text/html")
            
            # Enviar
            result = msg.send()
            
            if result:
                self.stdout.write(f'✅ {recipient.email}')
                
                # Log de entrega
                EmailDeliveryLog.objects.create(
                    recipient=recipient,
                    campaign=recipient.campaign,
                    log_type='send_attempt',
                    smtp_response='Email sent successfully'
                )
                
                return True
            else:
                self.stdout.write(f'❌ {recipient.email} - Send failed')
                return False
                
        except Exception as e:
            self.stdout.write(f'❌ {recipient.email} - Error: {e}')
            
            # Log de error
            EmailDeliveryLog.objects.create(
                recipient=recipient,
                campaign=recipient.campaign,
                log_type='delivery_failure',
                error_message=str(e)
            )
            
            return False

    def handle_exception(self, e):
        """Maneja excepciones del comando"""
        logger.error(f"Error en comando enviar_campana_email: {e}")
        self.stdout.write(self.style.ERROR(f'❌ Error crítico: {e}'))