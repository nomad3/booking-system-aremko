from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from ventas.models import MailParaEnviar, Contact
import zoneinfo


class Command(BaseCommand):
    help = "Envía emails programados con control de horarios (8:00-18:00) y límite por lote"

    def add_arguments(self, parser):
        parser.add_argument("--batch-size", type=int, default=2,
                            help="Número de emails a enviar por ejecución (default: 2)")
        parser.add_argument("--ignore-schedule", action="store_true",
                            help="Ignorar horario y enviar siempre")

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        ignore_schedule = options["ignore_schedule"]

        # Verificar horario (8:00 - 18:00 Chile)
        if not ignore_schedule:
            chile_tz = zoneinfo.ZoneInfo('America/Santiago')
            now_chile = timezone.now().astimezone(chile_tz)
            hour = now_chile.hour

            if hour < 8 or hour >= 18:
                self.stdout.write(f"Fuera de horario de envío (8:00-18:00). Hora actual: {hour:02d}:{now_chile.minute:02d}")
                return

        # Buscar emails pendientes
        emails_pendientes = MailParaEnviar.objects.filter(
            estado='PENDIENTE'
        ).order_by('prioridad', 'creado_en')[:batch_size]

        if not emails_pendientes:
            self.stdout.write("Sin emails pendientes para enviar.")
            return

        sent_count = 0
        failed_count = 0
        from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')
        reply_to = [getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')]

        for mail_obj in emails_pendientes:
            try:
                # Personalización con nombre
                contenido = mail_obj.contenido_html.replace('[Nombre]', mail_obj.nombre)
                
                # Crear email
                email = EmailMultiAlternatives(
                    subject=mail_obj.asunto,
                    body=contenido,
                    from_email=from_email,
                    to=[mail_obj.email],
                    reply_to=reply_to,
                )
                
                # Adjuntar HTML
                if '<' in contenido and '>' in contenido:
                    email.attach_alternative(contenido, 'text/html')

                # Enviar
                email.send()
                
                # Marcar como enviado
                mail_obj.marcar_como_enviado()
                
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f"✅ Enviado a: {mail_obj.nombre} ({mail_obj.email})"))
                
            except Exception as e:
                mail_obj.marcar_como_fallido()
                failed_count += 1
                self.stderr.write(self.style.ERROR(f"❌ Error enviando a {mail_obj.email}: {e}"))

        # Contar pendientes restantes
        pendientes_restantes = MailParaEnviar.objects.filter(estado='PENDIENTE').count()
        
        # Resumen
        self.stdout.write(f"📊 Lote completado: {sent_count} enviados, {failed_count} fallidos. Pendientes restantes: {pendientes_restantes}")
        
        if pendientes_restantes == 0:
            self.stdout.write(self.style.SUCCESS("🎉 ¡Campaña completada! No quedan emails pendientes."))