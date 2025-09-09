from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from ventas.models import CommunicationLog, Contact


class Command(BaseCommand):
    help = "Envía emails PENDING de campaña (goteo por lotes)."

    def add_arguments(self, parser):
        parser.add_argument("--template-path", default="/app/email_prueba.html",
                            help="Ruta del archivo HTML a usar como cuerpo (default: /app/email_prueba.html)")
        parser.add_argument("--subject", default="🌿 Reuniones con Resultados: Productividad + Bienestar en un solo lugar",
                            help="Asunto del correo")
        parser.add_argument("--batch-size", type=int, default=5,
                            help="Número de emails a enviar por ejecución (default: 5)")
        parser.add_argument("--use-stored-content", action="store_true",
                            help="Usar asunto y contenido almacenado en cada CommunicationLog")

    def handle(self, *args, **options):
        # Respetar flag global si existe
        if hasattr(settings, 'COMMUNICATION_EMAIL_ENABLED') and not settings.COMMUNICATION_EMAIL_ENABLED:
            self.stdout.write(self.style.WARNING("COMMUNICATION_EMAIL_ENABLED=False. Saliendo."))
            return

        batch_size = options["batch_size"]
        use_stored_content = options["use_stored_content"]
        fallback_subject = options["subject"]
        template_path = options["template_path"]

        # Cargar plantilla de fallback
        fallback_body = "Hola [Nombre],"
        try:
            with open(template_path, encoding="utf-8") as f:
                fallback_body = f.read()
        except Exception:
            pass

        # Buscar pendientes
        msg_types = dict(CommunicationLog.MESSAGE_TYPES)
        promo_key = 'PROMOTIONAL' if 'PROMOTIONAL' in msg_types else 'PROMOCIONAL'

        pending_logs = CommunicationLog.objects.filter(
            communication_type='EMAIL',
            message_type=promo_key,
            status='PENDING'
        ).order_by('created_at', 'id')[:batch_size]

        if not pending_logs:
            self.stdout.write("Sin pendientes.")
            return

        sent_count = 0
        failed_count = 0
        from_email = getattr(settings, 'EMAIL_HOST_USER', None) or getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')
        reply_to = [getattr(settings, 'VENTAS_FROM_EMAIL', 'ventas@aremko.cl')]

        for log in pending_logs:
            try:
                # Determinar asunto y contenido
                if use_stored_content and log.subject and log.content:
                    subject = log.subject
                    body_template = log.content
                else:
                    subject = fallback_subject
                    body_template = fallback_body

                # Personalización básica
                contact = Contact.objects.filter(email=log.destination).first()
                nombre = (contact.first_name if contact and contact.first_name else '').strip()
                body = body_template.replace('[Nombre]', nombre or 'Hola')

                # Crear email
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

                # Enviar
                email.send()
                
                # Marcar como enviado
                log.subject = subject
                log.content = body
                log.mark_as_sent()
                
                sent_count += 1
                self.stdout.write(self.style.SUCCESS(f"Enviado a: {log.destination}"))
                
            except Exception as e:
                log.status = 'FAILED'
                if not log.subject:
                    log.subject = subject
                if not log.content:
                    log.content = body_template
                log.save(update_fields=['status', 'content', 'subject'])
                failed_count += 1
                self.stderr.write(self.style.ERROR(f"Error enviando a {log.destination}: {e}"))

        # Actualizar progreso en cache
        from django.core.cache import cache
        cache_key = 'csv_campaign_progress'
        progress = cache.get(cache_key, {})
        if progress and isinstance(progress, dict):
            progress['sent'] = progress.get('sent', 0) + sent_count
            progress['failed'] = progress.get('failed', 0) + failed_count
            
            # Contar pendientes restantes
            pending_count = CommunicationLog.objects.filter(
                communication_type='EMAIL',
                message_type=promo_key,
                status='PENDING'
            ).count()
            progress['pending'] = pending_count
            
            if pending_count == 0:
                progress['status'] = 'completed'
                progress['message'] = f'🎉 Campaña completada! {progress.get("sent", 0)} emails enviados exitosamente.'
            
            cache.set(cache_key, progress, 3600)

        # Resumen final
        total_remaining = CommunicationLog.objects.filter(
            communication_type='EMAIL',
            message_type=promo_key,
            status='PENDING'
        ).count()
        
        self.stdout.write(f"Lote completado: {sent_count} enviados, {failed_count} fallidos. Pendientes restantes: {total_remaining}")

