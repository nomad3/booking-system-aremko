from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from ventas.models import Campaign


class Command(BaseCommand):
    help = "Envía un email de prueba de campaña a un destinatario único (no usa colas)."

    def add_arguments(self, parser):
        parser.add_argument("--to", required=True, help="Email destino, ej: test@example.com")
        parser.add_argument("--subject", required=False, help="Asunto a enviar si no se usa campaña")
        parser.add_argument("--body", required=False, help="Cuerpo (texto plano o HTML simple)")
        parser.add_argument("--body-file", dest="body_file", required=False, help="Ruta a archivo con el cuerpo (HTML)")
        parser.add_argument("--campaign-id", type=int, required=False, help="ID de Campaign para usar sus plantillas")

    def handle(self, *args, **options):
        to_email = options["to"].strip()
        subject = (options.get("subject") or "").strip()
        body = (options.get("body") or "").strip()
        body_file = options.get("body_file")

        if body_file:
            try:
                with open(body_file, 'r', encoding='utf-8') as f:
                    body = f.read()
            except FileNotFoundError:
                raise CommandError(f"Archivo no encontrado: {body_file}")
        campaign_id = options.get("campaign_id")

        if campaign_id:
            try:
                campaign = Campaign.objects.get(id=campaign_id)
            except Campaign.DoesNotExist:
                raise CommandError(f"Campaign id {campaign_id} no existe")

            # Usar plantilla de la campaña si existe
            if campaign.email_subject_template:
                subject = campaign.email_subject_template
            if campaign.email_body_template:
                body = campaign.email_body_template

        if not subject or not body:
            raise CommandError("Debe especificar --subject y --body, o bien --campaign-id con plantillas definidas.")

        from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')

        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email,
            to=[to_email],
            reply_to=[getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')],
        )
        # Adjuntar como HTML alternativo si parece HTML
        if "<" in body and ">" in body:
            email.attach_alternative(body, "text/html")

        email.send()

        self.stdout.write(self.style.SUCCESS(f"Email de prueba enviado a {to_email}"))

