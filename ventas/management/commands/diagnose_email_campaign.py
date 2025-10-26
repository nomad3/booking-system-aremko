# -*- coding: utf-8 -*-
"""
Management command para diagnosticar campañas de email avanzadas
Uso: python manage.py diagnose_email_campaign --campaign-name "marzo 2025 hasta 100 mil"
"""

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta
import pytz

from ventas.models import EmailCampaign, EmailRecipient, EmailDeliveryLog

class Command(BaseCommand):
    help = 'Diagnostica el estado de una campaña de email específica'

    def add_arguments(self, parser):
        parser.add_argument(
            '--campaign-name',
            type=str,
            help='Nombre de la campaña a diagnosticar'
        )
        parser.add_argument(
            '--campaign-id',
            type=int,
            help='ID de la campaña a diagnosticar'
        )
        parser.add_argument(
            '--list-all',
            action='store_true',
            help='Mostrar todas las campañas disponibles'
        )

    def handle(self, *args, **options):
        """
        Diagnostica el estado de una campaña específica
        """
        campaign_name = options.get('campaign_name')
        campaign_id = options.get('campaign_id')
        list_all = options.get('list_all')

        if list_all:
            self.list_all_campaigns()
            return

        # Buscar la campaña
        campaign = None
        if campaign_id:
            try:
                campaign = EmailCampaign.objects.get(id=campaign_id)
            except EmailCampaign.DoesNotExist:
                raise CommandError(f'No se encontró campaña con ID {campaign_id}')
        elif campaign_name:
            campaigns = EmailCampaign.objects.filter(name__icontains=campaign_name)
            if not campaigns.exists():
                raise CommandError(f'No se encontró campaña con nombre "{campaign_name}"')
            elif campaigns.count() > 1:
                self.stdout.write("🔍 Se encontraron múltiples campañas:")
                for camp in campaigns:
                    self.stdout.write(f"   - ID {camp.id}: {camp.name} ({camp.get_status_display()})")
                raise CommandError('Especifica el ID exacto con --campaign-id')
            campaign = campaigns.first()
        else:
            raise CommandError('Debes especificar --campaign-name, --campaign-id, o --list-all')

        # Diagnosticar la campaña
        self.diagnose_campaign(campaign)

    def list_all_campaigns(self):
        """Lista todas las campañas disponibles"""
        campaigns = EmailCampaign.objects.all().order_by('-created_at')
        
        self.stdout.write("📋 TODAS LAS CAMPAÑAS DISPONIBLES:")
        self.stdout.write("=" * 80)
        
        for campaign in campaigns:
            progress = f"{campaign.emails_sent}/{campaign.total_recipients}"
            percentage = campaign.progress_percentage
            
            self.stdout.write(f"🔸 ID {campaign.id}: {campaign.name}")
            self.stdout.write(f"   Estado: {campaign.get_status_display()}")
            self.stdout.write(f"   Progreso: {progress} ({percentage:.1f}%)")
            self.stdout.write(f"   Creada: {campaign.created_at.strftime('%Y-%m-%d %H:%M')}")
            self.stdout.write("")

    def diagnose_campaign(self, campaign):
        """Diagnostica una campaña específica"""
        self.stdout.write("🔍 DIAGNÓSTICO DE CAMPAÑA DE EMAIL")
        self.stdout.write("=" * 60)
        
        # 1. Información básica
        self.stdout.write("📊 INFORMACIÓN BÁSICA:")
        self.stdout.write(f"   • Nombre: {campaign.name}")
        self.stdout.write(f"   • ID: {campaign.id}")
        self.stdout.write(f"   • Estado: {campaign.get_status_display()}")
        self.stdout.write(f"   • Creada: {campaign.created_at.strftime('%Y-%m-%d %H:%M')}")
        self.stdout.write(f"   • Creada por: {campaign.created_by.username if campaign.created_by else 'N/A'}")
        self.stdout.write("")

        # 2. Estadísticas generales
        self.stdout.write("📈 ESTADÍSTICAS GENERALES:")
        self.stdout.write(f"   • Total destinatarios: {campaign.total_recipients}")
        self.stdout.write(f"   • Emails enviados: {campaign.emails_sent}")
        self.stdout.write(f"   • Emails entregados: {campaign.emails_delivered}")
        self.stdout.write(f"   • Emails abiertos: {campaign.emails_opened}")
        self.stdout.write(f"   • Emails con click: {campaign.emails_clicked}")
        self.stdout.write(f"   • Emails rebotados: {campaign.emails_bounced}")
        self.stdout.write(f"   • Progreso: {campaign.progress_percentage:.1f}%")
        self.stdout.write("")

        # 3. Análisis de destinatarios
        self.stdout.write("👥 ANÁLISIS DE DESTINATARIOS:")
        recipients_stats = EmailRecipient.objects.filter(campaign=campaign).values('status').annotate(count=Count('status'))
        
        for stat in recipients_stats:
            status_display = dict(EmailRecipient.RECIPIENT_STATUS_CHOICES).get(stat['status'], stat['status'])
            self.stdout.write(f"   • {status_display}: {stat['count']}")
        
        # Destinatarios pendientes
        pending_recipients = EmailRecipient.objects.filter(
            campaign=campaign,
            status='pending',
            send_enabled=True
        )
        self.stdout.write(f"   • Pendientes habilitados: {pending_recipients.count()}")
        self.stdout.write("")

        # 4. Configuración de envío
        self.stdout.write("⚙️ CONFIGURACIÓN DE ENVÍO:")
        schedule_config = campaign.schedule_config
        if schedule_config:
            self.stdout.write(f"   • Horario: {schedule_config.get('start_time', 'N/A')} - {schedule_config.get('end_time', 'N/A')}")
            self.stdout.write(f"   • Tamaño de lote: {schedule_config.get('batch_size', 'N/A')}")
            self.stdout.write(f"   • Intervalo: {schedule_config.get('interval_minutes', 'N/A')} minutos")
            self.stdout.write(f"   • Zona horaria: {schedule_config.get('timezone', 'N/A')}")
            self.stdout.write(f"   • IA habilitada: {schedule_config.get('ai_enabled', 'N/A')}")
        else:
            self.stdout.write("   • No hay configuración de horarios")
        self.stdout.write("")

        # 5. Verificar si está en horario de envío
        self.stdout.write("🕐 ESTADO ACTUAL DE ENVÍO:")
        in_schedule, reason = self.check_schedule(campaign)
        self.stdout.write(f"   • En horario de envío: {'Sí' if in_schedule else 'No'}")
        if not in_schedule:
            self.stdout.write(f"   • Razón: {reason}")
        self.stdout.write("")

        # 6. Últimos destinatarios procesados
        self.stdout.write("📝 ÚLTIMOS 10 DESTINATARIOS:")
        recent_recipients = EmailRecipient.objects.filter(campaign=campaign).order_by('-sent_at', '-id')[:10]
        
        for recipient in recent_recipients:
            sent_time = recipient.sent_at.strftime('%H:%M') if recipient.sent_at else 'N/A'
            self.stdout.write(f"   • {recipient.email} - {recipient.get_status_display()} - {sent_time}")
        self.stdout.write("")

        # 7. Próximos a enviar
        if pending_recipients.exists():
            self.stdout.write("📤 PRÓXIMOS 5 A ENVIAR:")
            next_recipients = pending_recipients[:5]
            for recipient in next_recipients:
                scheduled = recipient.scheduled_at.strftime('%H:%M') if recipient.scheduled_at else 'Inmediato'
                self.stdout.write(f"   • {recipient.email} - Programado: {scheduled}")
        else:
            self.stdout.write("📤 PRÓXIMOS A ENVIAR: Ninguno (campaña completada o pausada)")
        
        self.stdout.write("")

        # 8. Recomendaciones
        self.stdout.write("💡 RECOMENDACIONES:")
        if campaign.status == 'paused':
            self.stdout.write("   ⚠️ La campaña está PAUSADA. Para reanudar:")
            self.stdout.write("   python manage.py enviar_campana_email --campaign-id {} --auto".format(campaign.id))
        elif campaign.status == 'sending' and pending_recipients.exists():
            if not in_schedule:
                self.stdout.write(f"   ⏰ Fuera de horario de envío. {reason}")
                self.stdout.write("   La campaña se reanudará automáticamente en horario hábil.")
            else:
                self.stdout.write("   ✅ La campaña debería estar enviándose automáticamente.")
                self.stdout.write("   Verifica que el cron job esté configurado:")
                self.stdout.write("   */6 * * * * python manage.py enviar_campana_email --auto")
        elif campaign.status == 'completed':
            self.stdout.write("   ✅ Campaña completada exitosamente.")
        elif pending_recipients.exists():
            self.stdout.write("   🚀 Para iniciar/continuar el envío:")
            self.stdout.write("   python manage.py enviar_campana_email --campaign-id {} --auto".format(campaign.id))
        
        self.stdout.write("")
        self.stdout.write("🔚 FIN DEL DIAGNÓSTICO")

    def check_schedule(self, campaign):
        """Verifica si la campaña está en horario de envío"""
        schedule_config = campaign.schedule_config
        if not schedule_config:
            return True, "Sin restricciones de horario"
        
        # Configurar zona horaria
        timezone_name = schedule_config.get('timezone', 'America/Santiago')
        try:
            tz = pytz.timezone(timezone_name)
        except:
            tz = pytz.timezone('America/Santiago')
        
        now = timezone.now().astimezone(tz)
        current_time = now.time()
        
        # Verificar horario
        start_time_str = schedule_config.get('start_time', '08:00')
        end_time_str = schedule_config.get('end_time', '21:00')
        
        try:
            start_time = datetime.strptime(start_time_str, '%H:%M').time()
            end_time = datetime.strptime(end_time_str, '%H:%M').time()
        except:
            return True, "Error en formato de horario"
        
        if start_time <= current_time <= end_time:
            return True, f"Hora actual {current_time.strftime('%H:%M')} está en rango"
        else:
            return False, f"Hora actual {current_time.strftime('%H:%M')} fuera del rango {start_time_str}-{end_time_str}"