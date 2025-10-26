# -*- coding: utf-8 -*-
"""
Comando para enviar campaña de giftcard cada 6 minutos
Envía 2 emails por ejecución
"""

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.utils import timezone
from ventas.models import MailParaEnviar, Contact
import pytz


class Command(BaseCommand):
    help = "Envía campaña de giftcard cada 6 minutos (2 emails por ejecución)"

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
            chile_tz = pytz.timezone('America/Santiago')
            now_chile = timezone.now().astimezone(chile_tz)
            hour = now_chile.hour
            
            if hour < 8 or hour >= 18:
                self.stdout.write(f"Fuera de horario de envío (8:00-18:00). Hora actual: {hour:02d}:{now_chile.minute:02d}")
                return

        # Buscar emails de campaña de giftcard pendientes
        emails_pendientes = MailParaEnviar.objects.filter(
            estado='PENDIENTE',
            asunto__icontains='giftcard'
        ).order_by('prioridad', 'creado_en')[:batch_size]

        if not emails_pendientes:
            self.stdout.write("Sin emails de campaña giftcard pendientes para enviar.")
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
                    bcc=['aremkospa@gmail.com', getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')]
                )
                
                # Agregar contenido HTML
                email.attach_alternative(contenido, "text/html")
                
                # Enviar email
                email.send()
                
                # Marcar como enviado
                mail_obj.estado = 'ENVIADO'
                mail_obj.fecha_envio = timezone.now()
                mail_obj.save()
                
                sent_count += 1
                self.stdout.write(f"✅ Email enviado a {mail_obj.email} - {mail_obj.nombre}")
                
            except Exception as e:
                # Marcar como fallido
                mail_obj.estado = 'FALLIDO'
                mail_obj.observaciones = f"Error: {str(e)}"
                mail_obj.save()
                
                failed_count += 1
                self.stdout.write(f"❌ Error enviando a {mail_obj.email}: {str(e)}")

        # Resumen
        self.stdout.write(f"\n📊 Resumen de envío:")
        self.stdout.write(f"   ✅ Enviados: {sent_count}")
        self.stdout.write(f"   ❌ Fallidos: {failed_count}")
        self.stdout.write(f"   📧 Total procesados: {sent_count + failed_count}")
        
        # Mostrar próximos emails en cola
        pendientes_restantes = MailParaEnviar.objects.filter(
            estado='PENDIENTE',
            asunto__icontains='giftcard'
        ).count()
        
        if pendientes_restantes > 0:
            self.stdout.write(f"   ⏳ Pendientes en cola: {pendientes_restantes}")
        else:
            self.stdout.write(f"   🎉 ¡Campaña completada! No hay más emails pendientes.")