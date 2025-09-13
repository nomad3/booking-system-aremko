# -*- coding: utf-8 -*-
"""
Comando para ejecutar la campaña de giftcard para clientes de enero 2025
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from datetime import datetime, date
from ventas.models import Cliente, VentaReserva, ReservaServicio, CommunicationLog, Campaign
from django.db.models import Q, Count, Sum
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Ejecuta la campaña de giftcard para clientes de enero 2025"

    def add_arguments(self, parser):
        parser.add_argument('--batch-size', type=int, default=10, help='Número de emails a enviar por lote')
        parser.add_argument('--dry-run', action='store_true', help='Simular envío sin enviar emails reales')
        parser.add_argument('--campaign-id', type=int, help='ID de la campaña específica a ejecutar')

    def handle(self, *args, **options):
        batch_size = options.get('batch_size', 10)
        dry_run = options.get('dry_run', False)
        campaign_id = options.get('campaign_id')
        
        self.stdout.write("🚀 Iniciando campaña de giftcard para clientes de enero 2025...")
        
        # Obtener campaña
        if campaign_id:
            try:
                campaign = Campaign.objects.get(id=campaign_id)
            except Campaign.DoesNotExist:
                self.stdout.write(self.style.ERROR(f"❌ Campaña {campaign_id} no encontrada"))
                return
        else:
            # Buscar campaña de giftcard
            campaign = Campaign.objects.filter(
                name__icontains="giftcard",
                name__icontains="enero"
            ).first()
            
            if not campaign:
                self.stdout.write(self.style.ERROR("❌ No se encontró campaña de giftcard para enero"))
                return
        
        self.stdout.write(f"📧 Campaña: {campaign.name}")
        
        # Obtener clientes objetivo
        clientes = self.get_target_clients()
        
        if not clientes.exists():
            self.stdout.write(self.style.WARNING("⚠️ No hay clientes objetivo para esta campaña"))
            return
        
        self.stdout.write(f"🎯 Clientes objetivo: {clientes.count()}")
        
        # Verificar emails ya enviados
        emails_enviados = CommunicationLog.objects.filter(
            message_type='PROMOCIONAL',
            subject__icontains='giftcard',
            status='SENT'
        ).count()
        
        self.stdout.write(f"📊 Emails ya enviados: {emails_enviados}")
        
        # Procesar lote
        clientes_pendientes = clientes.exclude(
            id__in=CommunicationLog.objects.filter(
                message_type='PROMOCIONAL',
                subject__icontains='giftcard',
                status__in=['SENT', 'PENDING']
            ).values_list('cliente_id', flat=True)
        )[:batch_size]
        
        if not clientes_pendientes.exists():
            self.stdout.write(self.style.SUCCESS("✅ Todos los clientes ya han recibido el email"))
            return
        
        self.stdout.write(f"📤 Enviando a {clientes_pendientes.count()} clientes...")
        
        # Enviar emails
        sent_count = 0
        failed_count = 0
        
        for cliente in clientes_pendientes:
            try:
                if dry_run:
                    self.stdout.write(f"   [DRY RUN] Enviando a {cliente.nombre} ({cliente.email})")
                    sent_count += 1
                else:
                    success = self.send_giftcard_email(cliente, campaign)
                    if success:
                        sent_count += 1
                        self.stdout.write(f"   ✅ Enviado a {cliente.nombre} ({cliente.email})")
                    else:
                        failed_count += 1
                        self.stdout.write(f"   ❌ Error enviando a {cliente.nombre} ({cliente.email})")
                        
            except Exception as e:
                failed_count += 1
                self.stdout.write(f"   ❌ Error enviando a {cliente.nombre}: {str(e)}")
                logger.error(f"Error enviando email a {cliente.email}: {str(e)}")
        
        # Resumen
        self.stdout.write(f"\n📊 Resumen del lote:")
        self.stdout.write(f"   ✅ Enviados: {sent_count}")
        self.stdout.write(f"   ❌ Fallidos: {failed_count}")
        
        if not dry_run:
            # Contar pendientes restantes
            pendientes_restantes = clientes.exclude(
                id__in=CommunicationLog.objects.filter(
                    message_type='PROMOCIONAL',
                    subject__icontains='giftcard',
                    status__in=['SENT', 'PENDING']
                ).values_list('cliente_id', flat=True)
            ).count()
            
            self.stdout.write(f"   ⏳ Pendientes restantes: {pendientes_restantes}")
            
            if pendientes_restantes == 0:
                self.stdout.write(self.style.SUCCESS("🎉 ¡Campaña completada! Todos los clientes han recibido el email"))

    def get_target_clients(self):
        """Obtiene los clientes objetivo para la campaña"""
        # Definir rango de enero 2025
        enero_inicio = date(2025, 1, 1)
        enero_fin = date(2025, 1, 31)
        
        # Buscar clientes que tuvieron reservas en enero 2025
        clientes = Cliente.objects.filter(
            ventareserva__reservaservicios__fecha_agendamiento__range=(enero_inicio, enero_fin),
            email__isnull=False,
            email__gt=''
        ).exclude(email='').distinct()
        
        return clientes

    def send_giftcard_email(self, cliente, campaign):
        """Envía el email de giftcard a un cliente"""
        try:
            # Personalizar plantilla
            subject = campaign.email_subject_template
            body_html = campaign.email_body_template
            
            # Reemplazar placeholders
            if '{nombre_cliente}' in body_html:
                body_html = body_html.replace('{nombre_cliente}', cliente.nombre)
            if '{apellido_cliente}' in body_html:
                apellido = getattr(cliente, 'apellido', '') or ''
                body_html = body_html.replace('{apellido_cliente}', apellido)
            
            # Crear email
            email = EmailMultiAlternatives(
                subject=subject,
                body=body_html,
                from_email=getattr(settings, 'EMAIL_HOST_USER', 'ventas@aremko.cl'),
                to=[cliente.email],
                bcc=['aremkospa@gmail.com', 'ventas@aremko.cl'],  # Copias automáticas
                reply_to=['ventas@aremko.cl']
            )
            
            # Adjuntar HTML
            email.attach_alternative(body_html, "text/html")
            
            # Enviar
            email.send()
            
            # Registrar en CommunicationLog
            CommunicationLog.objects.create(
                cliente=cliente,
                communication_type='EMAIL',
                message_type='PROMOCIONAL',
                subject=subject,
                content=body_html,
                destination=cliente.email,
                status='SENT',
                cost=0
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email a {cliente.email}: {str(e)}")
            return False