# -*- coding: utf-8 -*-
"""
Comando para probar el envío de emails con SendGrid
"""

from django.core.management.base import BaseCommand
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Prueba el envío de emails con SendGrid'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            help='Email de destino para la prueba',
            required=True
        )
        parser.add_argument(
            '--from-email',
            type=str,
            help='Email remitente (default: ventas@aremko.cl)',
            default='ventas@aremko.cl'
        )

    def handle(self, *args, **options):
        to_email = options['to']
        from_email = options.get('from_email', 'ventas@aremko.cl')

        self.stdout.write(self.style.SUCCESS('=== TEST DE SENDGRID ==='))
        self.stdout.write(f'Backend configurado: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        self.stdout.write(f'VENTAS_FROM_EMAIL: {settings.VENTAS_FROM_EMAIL}')
        self.stdout.write(f'Enviando desde: {from_email}')
        self.stdout.write(f'Enviando a: {to_email}')
        self.stdout.write('')

        # Test 1: Email simple con send_mail
        self.stdout.write('📧 Test 1: Email simple con send_mail()')
        try:
            send_mail(
                subject='[TEST] Email desde Aremko - Prueba Simple',
                message='Este es un email de prueba enviado desde Django usando SendGrid.',
                from_email=from_email,
                recipient_list=[to_email],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS('✅ Email simple enviado exitosamente'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error enviando email simple: {str(e)}'))
            logger.error(f'Error en test de email simple: {str(e)}', exc_info=True)

        self.stdout.write('')

        # Test 2: Email HTML con EmailMultiAlternatives
        self.stdout.write('📧 Test 2: Email HTML con EmailMultiAlternatives()')
        try:
            subject = '[TEST] Email HTML desde Aremko'
            text_content = 'Este es un email de prueba con HTML.'
            html_content = '''
            <html>
            <head>
                <style>
                    body { font-family: Arial, sans-serif; }
                    .header { background-color: #417690; color: white; padding: 20px; }
                    .content { padding: 20px; }
                    .footer { background-color: #f0f0f0; padding: 10px; text-align: center; }
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>🎉 Test de Email HTML</h1>
                </div>
                <div class="content">
                    <h2>¡Hola desde Aremko!</h2>
                    <p>Este es un email de prueba enviado desde Django usando SendGrid.</p>
                    <p><strong>Configuración actual:</strong></p>
                    <ul>
                        <li>Backend: SendGrid (Anymail)</li>
                        <li>From: {from_email}</li>
                        <li>Dominio verificado: em786.aremko.cl</li>
                    </ul>
                    <p>Si recibes este email, ¡la configuración está funcionando correctamente! ✅</p>
                </div>
                <div class="footer">
                    <p>Aremko Aguas Calientes & Spa - Puerto Varas, Chile</p>
                </div>
            </body>
            </html>
            '''.format(from_email=from_email)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=from_email,
                to=[to_email],
                reply_to=[from_email],
            )
            msg.attach_alternative(html_content, "text/html")
            msg.send()

            self.stdout.write(self.style.SUCCESS('✅ Email HTML enviado exitosamente'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error enviando email HTML: {str(e)}'))
            logger.error(f'Error en test de email HTML: {str(e)}', exc_info=True)

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=== FIN DEL TEST ==='))
        self.stdout.write('')
        self.stdout.write('📊 Revisa tu bandeja de entrada en: ' + to_email)
        self.stdout.write('📊 También revisa el dashboard de SendGrid:')
        self.stdout.write('   https://app.sendgrid.com/statistics')
