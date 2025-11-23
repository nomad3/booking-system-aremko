# -*- coding: utf-8 -*-
"""
Comando para probar la configuración de SendGrid
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Prueba el envío de emails con SendGrid'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            default='aremkospa@gmail.com',
            help='Email de destino para la prueba'
        )

    def handle(self, *args, **options):
        to_email = options['to']
        
        self.stdout.write(self.style.WARNING('🔍 Verificando configuración de SendGrid...'))
        
        # Verificar configuración
        self.stdout.write(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        self.stdout.write(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        
        if hasattr(settings, 'ANYMAIL'):
            self.stdout.write(self.style.SUCCESS("✅ ANYMAIL configurado"))
            api_key = settings.ANYMAIL.get('SENDGRID_API_KEY', '')
            if api_key:
                masked_key = f"{api_key[:10]}...{api_key[-10:]}" if len(api_key) > 20 else "***"
                self.stdout.write(f"SENDGRID_API_KEY: {masked_key}")
            else:
                self.stdout.write(self.style.ERROR("❌ SENDGRID_API_KEY no encontrada"))
                return
        else:
            self.stdout.write(self.style.ERROR("❌ ANYMAIL no está configurado"))
            return
        
        # Enviar email de prueba
        self.stdout.write(self.style.WARNING(f'\n📧 Enviando email de prueba a {to_email}...'))
        
        try:
            send_mail(
                subject='🧪 Prueba de SendGrid - Aremko',
                message='Este es un email de prueba enviado desde Django usando SendGrid (Twilio).\n\n'
                        'Si recibes este mensaje, significa que la configuración está funcionando correctamente.\n\n'
                        '✅ SendGrid está activo\n'
                        '✅ Los emails ahora se envían a través de Twilio SendGrid\n'
                        '✅ Ya no se usa SMTP tradicional\n\n'
                        'Saludos,\n'
                        'Sistema Aremko',
                html_message='<html><body>'
                            '<h2>🧪 Prueba de SendGrid - Aremko</h2>'
                            '<p>Este es un email de prueba enviado desde Django usando <strong>SendGrid (Twilio)</strong>.</p>'
                            '<p>Si recibes este mensaje, significa que la configuración está funcionando correctamente.</p>'
                            '<ul>'
                            '<li>✅ SendGrid está activo</li>'
                            '<li>✅ Los emails ahora se envían a través de Twilio SendGrid</li>'
                            '<li>✅ Ya no se usa SMTP tradicional</li>'
                            '</ul>'
                            '<p>Saludos,<br><strong>Sistema Aremko</strong></p>'
                            '</body></html>',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            
            self.stdout.write(self.style.SUCCESS(f'\n✅ Email enviado exitosamente a {to_email}'))
            self.stdout.write(self.style.SUCCESS('✅ SendGrid está funcionando correctamente'))
            self.stdout.write(self.style.WARNING('\n📊 Verifica en SendGrid Dashboard:'))
            self.stdout.write('   https://app.sendgrid.com/email_activity')
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'\n❌ Error al enviar email: {str(e)}'))
            logger.error(f"Error en test_sendgrid: {str(e)}", exc_info=True)
