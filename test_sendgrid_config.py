#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para probar la configuración de SendGrid
Ejecutar desde Render Shell o localmente con: python test_sendgrid_config.py
"""

import os
import sys
import django

# Configurar Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings


def test_sendgrid_configuration():
    """
    Prueba la configuración de SendGrid enviando un email de prueba
    """
    print("=" * 60)
    print("PRUEBA DE CONFIGURACIÓN DE SENDGRID")
    print("=" * 60)

    # 1. Verificar variables de entorno
    print("\n1. VERIFICANDO VARIABLES DE ENTORNO:")
    print("-" * 60)

    sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
    if sendgrid_key:
        masked_key = sendgrid_key[:10] + "..." + sendgrid_key[-10:] if len(sendgrid_key) > 20 else "***"
        print(f"   ✅ SENDGRID_API_KEY: {masked_key}")
    else:
        print("   ❌ SENDGRID_API_KEY no encontrada")
        return False

    default_from = os.getenv('DEFAULT_FROM_EMAIL', settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else '')
    if default_from:
        print(f"   ✅ DEFAULT_FROM_EMAIL: {default_from}")
    else:
        print("   ⚠️  DEFAULT_FROM_EMAIL no configurado")

    # 2. Verificar configuración de Django
    print("\n2. VERIFICANDO CONFIGURACIÓN DE DJANGO:")
    print("-" * 60)
    print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")

    # 3. Enviar email de prueba
    print("\n3. ENVIANDO EMAIL DE PRUEBA:")
    print("-" * 60)

    # Email de destino (puedes cambiarlo)
    email_destino = input("   Ingresa el email de destino para la prueba (o presiona Enter para usar aremkospa@gmail.com): ").strip()
    if not email_destino:
        email_destino = "aremkospa@gmail.com"

    print(f"   Enviando a: {email_destino}")

    try:
        resultado = send_mail(
            subject='✅ Prueba de SendGrid - Aremko',
            message='Este es un email de prueba para verificar la configuración de SendGrid.',
            from_email=default_from or 'aremkospa@gmail.com',
            recipient_list=[email_destino],
            html_message='''
                <html>
                <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f5f5f5;">
                    <div style="max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        <h1 style="color: #2c5f2d; margin-bottom: 20px;">✅ Prueba de SendGrid</h1>
                        <p style="font-size: 16px; line-height: 1.6; color: #333;">
                            ¡Felicidades! Tu configuración de <strong>SendGrid</strong> está funcionando correctamente.
                        </p>
                        <p style="font-size: 16px; line-height: 1.6; color: #333;">
                            Este email fue enviado desde tu aplicación de <strong>Aremko Booking System</strong>.
                        </p>
                        <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                        <p style="font-size: 14px; color: #666;">
                            <strong>Configuración actual:</strong><br>
                            Remitente: {from_email}<br>
                            Backend: Django SMTP → SendGrid<br>
                            Estado: ✅ Activo
                        </p>
                    </div>
                </body>
                </html>
            '''.format(from_email=default_from or 'aremkospa@gmail.com'),
            fail_silently=False,
        )

        if resultado > 0:
            print("\n" + "=" * 60)
            print("✅ ¡EMAIL ENVIADO EXITOSAMENTE!")
            print("=" * 60)
            print(f"\n   📧 Revisa tu bandeja de entrada en: {email_destino}")
            print("   📁 Si no lo ves, revisa la carpeta de Spam/Promociones")
            print("\n   ✅ SendGrid está configurado correctamente")
            print("   ✅ Ya puedes enviar campañas de email a tus clientes")
            print()
            return True
        else:
            print("\n❌ Error: No se pudo enviar el email")
            return False

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR AL ENVIAR EMAIL")
        print("=" * 60)
        print(f"\n   Error: {str(e)}")
        print("\n   Posibles causas:")
        print("   1. SENDGRID_API_KEY incorrecta")
        print("   2. Sender Identity no verificado en SendGrid")
        print("   3. DEFAULT_FROM_EMAIL no coincide con el verificado")
        print()
        return False


if __name__ == '__main__':
    print("\n")
    success = test_sendgrid_configuration()
    print("\n")
    sys.exit(0 if success else 1)
