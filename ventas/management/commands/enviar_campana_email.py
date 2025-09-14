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

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n🚀 INICIANDO ENVÍO DE CAMPAÑAS EMAIL'))
        
        batch_size = options['batch_size']
        interval_minutes = options['interval']
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('⚠️ MODO DRY-RUN: No se enviarán emails reales'))
        
        # Verificar horario de envío
        if not self.is_sending_time():
            self.stdout.write(self.style.WARNING('⏰ Fuera del horario de envío (8:00-18:00). Saliendo.'))
            return
        
        if options['auto']:
            # Modo automático: procesar todas las campañas listas
            campaigns = EmailCampaign.objects.filter(status='ready')
            self.stdout.write(f'📊 Encontradas {campaigns.count()} campañas listas para envío')
            
            for campaign in campaigns:
                self.process_campaign(campaign, batch_size, interval_minutes, dry_run)
        
        elif options['campaign_id']:
            # Modo manual: procesar campaña específica
            try:
                campaign = EmailCampaign.objects.get(id=options['campaign_id'])
                if campaign.status != 'ready':
                    raise CommandError(f'❌ Campaña {campaign.id} no está lista para envío (estado: {campaign.status})')
                
                self.process_campaign(campaign, batch_size, interval_minutes, dry_run)
                
            except EmailCampaign.DoesNotExist:
                raise CommandError(f'❌ Campaña con ID {options["campaign_id"]} no encontrada')
        else:
            raise CommandError('❌ Debe especificar --campaign-id o --auto')

    def is_sending_time(self):
        """Verifica si estamos en horario de envío (8:00 - 18:00)"""
        now = timezone.now()
        chile_time = now.astimezone(timezone.get_fixed_timezone(-180))  # UTC-3
        current_hour = chile_time.hour
        return 8 <= current_hour <= 18

    def process_campaign(self, campaign, batch_size, interval_minutes, dry_run):
        """Procesa una campaña específica"""
        self.stdout.write(f'\n📧 Procesando campaña: {campaign.name}')
        
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
        for i in range(0, total_pending, batch_size):
            batch = pending_recipients[i:i + batch_size]
            
            self.stdout.write(f'\n📤 Enviando lote {i//batch_size + 1}: {len(batch)} emails')
            
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
            if i + batch_size < total_pending:
                self.stdout.write(f'⏸️ Pausa de {interval_minutes} minutos...')
                if not dry_run:
                    time.sleep(interval_minutes * 60)
        
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