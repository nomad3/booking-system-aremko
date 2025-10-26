# -*- coding: utf-8 -*-
"""
Comando para probar el envío de un email de prueba
"""

from django.core.management.base import BaseCommand
from django.core.mail import EmailMultiAlternatives
from django.conf import settings


class Command(BaseCommand):
    help = 'Envía un email de prueba para verificar configuración'

    def add_arguments(self, parser):
        parser.add_argument(
            '--to',
            type=str,
            required=True,
            help='Email destinatario para la prueba'
        )

    def handle(self, *args, **options):
        to_email = options['to']
        
        self.stdout.write(f'📧 Enviando email de prueba a: {to_email}')
        
        # Crear email de prueba
        subject = '🎁 Email de Prueba - Sistema Aremko'
        html_body = """
        <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #4299e1;">🚀 Sistema de Email Marketing - Prueba</h2>
                <p>¡Hola! Este es un email de prueba del sistema de campañas de Aremko.</p>
                
                <div style="background: #f7fafc; padding: 15px; border-radius: 8px; margin: 20px 0;">
                    <h3 style="color: #2d3748;">✅ Configuración Funcionando</h3>
                    <ul>
                        <li>✉️ SMTP configurado correctamente</li>
                        <li>🎨 HTML emails funcionando</li>
                        <li>📧 Sistema de campañas operativo</li>
                    </ul>
                </div>
                
                <p style="color: #718096;">
                    Fecha: <strong>{{ now }}</strong><br>
                    Sistema: <strong>Aremko Booking System</strong>
                </p>
                
                <hr style="margin: 20px 0;">
                <p style="font-size: 12px; color: #a0aec0;">
                    Este es un email automático del sistema de gestión Aremko.
                </p>
            </body>
        </html>
        """
        
        text_body = """
        🚀 Sistema de Email Marketing - Prueba
        
        ¡Hola! Este es un email de prueba del sistema de campañas de Aremko.
        
        ✅ Configuración Funcionando:
        - SMTP configurado correctamente
        - HTML emails funcionando  
        - Sistema de campañas operativo
        
        Sistema: Aremko Booking System
        """
        
        try:
            # Crear y enviar email
            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email]
            )
            
            # Agregar versión HTML
            msg.attach_alternative(html_body, "text/html")
            
            # Enviar
            result = msg.send()
            
            if result:
                self.stdout.write(self.style.SUCCESS(f'✅ Email enviado exitosamente a {to_email}'))
                self.stdout.write('📧 Revisa tu bandeja de entrada y spam.')
            else:
                self.stdout.write(self.style.ERROR(f'❌ Error enviando email a {to_email}'))
                
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error: {e}'))
            self.stdout.write('\n🔧 Posibles soluciones:')
            self.stdout.write('1. Verificar configuración SMTP en settings')
            self.stdout.write('2. Verificar variables de entorno EMAIL_*')
            self.stdout.write('3. Verificar conexión a internet')
            self.stdout.write('4. Verificar credenciales del proveedor de email')