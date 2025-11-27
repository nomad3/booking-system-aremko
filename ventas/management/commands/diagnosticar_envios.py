"""
Comando para verificar el estado de los envíos de campañas de email
"""
from django.core.management.base import BaseCommand
from ventas.models import EmailCampaign, EmailRecipient, EmailDeliveryLog
from django.utils import timezone

class Command(BaseCommand):
    help = 'Verifica el estado de los envíos de campañas de email'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('DIAGNÓSTICO DE ENVÍOS DE CAMPAÑAS'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

        # Últimas 5 campañas
        ultimas_campanas = EmailCampaign.objects.all().order_by('-created_at')[:5]

        if not ultimas_campanas.exists():
            self.stdout.write("No hay campañas creadas.")
            return

        for campana in ultimas_campanas:
            self.stdout.write(f'\n📧 Campaña: "{campana.name}" (ID: {campana.id})')
            self.stdout.write(f'   Estado: {campana.status}')
            self.stdout.write(f'   Creada: {campana.created_at.strftime("%Y-%m-%d %H:%M")}')
            
            recipients = campana.recipients.all()
            total = recipients.count()
            sent = recipients.filter(status='sent').count()
            pending = recipients.filter(status='pending').count()
            failed = recipients.filter(status='failed').count()
            
            self.stdout.write(f'   Destinatarios: Total {total} | Enviados {sent} | Pendientes {pending} | Fallidos {failed}')

            if failed > 0:
                self.stdout.write(self.style.ERROR(f'   ⚠️  Hay {failed} envíos fallidos. Últimos errores:'))
                failed_recipients = recipients.filter(status='failed')[:3]
                for r in failed_recipients:
                    self.stdout.write(f'      - {r.email}: {r.error_message}')

            # Logs de entrega recientes
            logs = EmailDeliveryLog.objects.filter(campaign=campana).order_by('-timestamp')[:3]
            if logs.exists():
                self.stdout.write(f'   📝 Últimos logs de entrega:')
                for log in logs:
                    status_icon = "✅" if log.log_type == 'send_attempt' else "❌"
                    self.stdout.write(f'      {status_icon} {log.timestamp.strftime("%H:%M:%S")}: {log.log_type} - {log.smtp_response or log.error_message}')
            else:
                self.stdout.write(f'   ℹ️  No hay logs de entrega registrados aún.')

        self.stdout.write('\n' + '=' * 80)
