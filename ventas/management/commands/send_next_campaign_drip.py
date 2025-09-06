from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from ventas.models import CommunicationLog, Contact


class Command(BaseCommand):
    help = "Envía el siguiente email PENDING de campaña (goteo 1 a la vez)."

    def add_arguments(self, parser):
        parser.add_argument("--template-path", default="/app/email_prueba.html",
                            help="Ruta del archivo HTML a usar como cuerpo (default: /app/email_prueba.html)")
        parser.add_argument("--subject", default="🌿 Reuniones con Resultados: Productividad + Bienestar en un solo lugar",
                            help="Asunto del correo")

    def handle(self, *args, **options):
        # Respetar flag global si existe
        if hasattr(settings, 'COMMUNICATION_EMAIL_ENABLED') and not settings.COMMUNICATION_EMAIL_ENABLED:
            self.stdout.write(self.style.WARNING("COMMUNICATION_EMAIL_ENABLED=False. Saliendo."))
            return

        subject = options["subject"]
        template_path = options["template_path"]

        # Cargar plantilla
        try:
            with open(template_path, encoding="utf-8") as f:
                body_tpl = f.read()
        except Exception:
            body_tpl = "Hola [Nombre],"

        # Buscar primer pendiente
        msg_types = dict(CommunicationLog.MESSAGE_TYPES)
        promo_key = 'PROMOTIONAL' if 'PROMOTIONAL' in msg_types else 'PROMOCIONAL'

        log = CommunicationLog.objects.filter(
            communication_type='EMAIL',
            message_type=promo_key,
            status='PENDING'
        ).order_by('created_at', 'id').first()

        if not log:
            self.stdout.write("Sin pendientes.")
            return

        # Personalización básica
        contact = Contact.objects.filter(email=log.destination).first()
        nombre = (contact.first_name if contact and contact.first_name else '').strip()
        body = body_tpl.replace('[Nombre]', nombre or 'Hola')

        from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')
        reply_to = [getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')]

        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[log.destination],
            reply_to=reply_to,
        )
        # Adjuntar HTML si corresponde
        if '<' in body and '>' in body:
            email.attach_alternative(body, 'text/html')

        try:
            email.send()
        except Exception as e:
            log.status = 'FAILED'
            log.content = body
            log.subject = subject
            log.save(update_fields=['status', 'content', 'subject'])
            self.stderr.write(self.style.ERROR(f"Error enviando a {log.destination}: {e}"))
            return

        # Marcar enviado
        log.subject = subject
        log.content = body
        log.mark_as_sent()
        self.stdout.write(self.style.SUCCESS(f"Enviado a: {log.destination}"))
        
        # Actualizar progreso en cache
        from django.core.cache import cache
        cache_key = 'csv_campaign_progress'
        progress = cache.get(cache_key, {})
        if progress and isinstance(progress, dict):
            progress['sent'] = progress.get('sent', 0) + 1
            # Contar pendientes restantes
            pending_count = CommunicationLog.objects.filter(
                communication_type='EMAIL',
                message_type=promo_key,
                status='PENDING'
            ).count()
            progress['pending'] = pending_count
            if pending_count == 0:
                progress['status'] = 'completed'
            cache.set(cache_key, progress, 3600)

