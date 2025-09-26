# -*- coding: utf-8 -*-
"""
Management command para enviar un email de prueba de la campaña
Uso: python manage.py send_campaign_test_email --email test@example.com --nombre "Juan Pérez" --empresa "Mi Empresa"
"""

from django.core.management.base import BaseCommand, CommandError
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.template import Template, Context
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Envía un email de prueba de la campaña de prospección'

    def add_arguments(self, parser):
        parser.add_argument(
            '--email',
            type=str,
            required=True,
            help='Email de destino para la prueba'
        )
        parser.add_argument(
            '--nombre',
            type=str,
            default='[Nombre]',
            help='Nombre del contacto para personalización'
        )
        parser.add_argument(
            '--empresa',
            type=str,
            default='[Empresa]',
            help='Nombre de la empresa para personalización'
        )

    def handle(self, *args, **options):
        """
        Envía un email de prueba con la plantilla de campaña
        """
        email = options['email']
        nombre = options['nombre']
        empresa = options['empresa']

        subject = "🏨 Reuniones que Inspiran: Descubre el Secreto de los Equipos Más Exitosos en Los Lagos"
        
        try:
            # Cargar y personalizar la plantilla
            template_path = 'templates/emails/prospecting_campaign.html'
            
            # Leer el archivo de plantilla
            with open(template_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            # Personalizar contenido
            template = Template(html_content)
            personalized_content = template.render(Context({
                'nombre': nombre,
                'empresa': empresa,
                'email': email
            }))
            
            # Crear email
            from_email = getattr(settings, 'VENTAS_FROM_EMAIL', settings.EMAIL_HOST_USER)
            
            email_msg = EmailMultiAlternatives(
                subject=subject,
                body=f"Email de prueba de campaña para {nombre} de {empresa}",  # Texto plano
                from_email=from_email,
                to=[email]
            )
            
            # Agregar contenido HTML
            email_msg.attach_alternative(personalized_content, "text/html")
            
            # Enviar
            email_msg.send()
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Email de prueba enviado exitosamente a {email}')
            )
            
            # Log para auditoría
            logger.info(f"Email de prueba enviado a {email} (nombre: {nombre}, empresa: {empresa})")
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error enviando email de prueba: {str(e)}')
            )
            logger.error(f"Error enviando email de prueba a {email}: {str(e)}")
            raise CommandError(f'Falló el envío del email: {str(e)}')