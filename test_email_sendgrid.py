#!/usr/bin/env python
"""
Script para probar el envío de correos con SendGrid
Ejecutar con: python test_email_sendgrid.py
"""

import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_sendgrid_connection():
    """Prueba la conexión y envío con SendGrid"""

    print("\n" + "="*50)
    print("PRUEBA DE CONFIGURACIÓN DE EMAIL - SENDGRID")
    print("="*50)

    # Verificar configuración
    print("\n📧 Configuración actual:")
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
    print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
    print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
    print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
    print(f"SENDGRID_API_KEY configurada: {'Sí' if os.getenv('SENDGRID_API_KEY') else 'No'}")

    if not os.getenv('SENDGRID_API_KEY'):
        print("\n❌ ERROR: No hay SENDGRID_API_KEY configurada")
        print("Configura la variable de entorno SENDGRID_API_KEY")
        return False

    # Intentar enviar correo de prueba
    print("\n📨 Intentando enviar correo de prueba...")

    try:
        # Pedir email de destino
        email_destino = input("\nIngresa el email de destino para la prueba: ").strip()
        if not email_destino:
            print("❌ Email de destino requerido")
            return False

        # Enviar correo
        result = send_mail(
            subject='Prueba de SendGrid - Aremko',
            message='Este es un correo de prueba desde el sistema Aremko.',
            html_message="""
            <h2>Prueba de SendGrid Exitosa ✅</h2>
            <p>Si recibes este correo, significa que SendGrid está funcionando correctamente.</p>
            <p><strong>Configuración:</strong></p>
            <ul>
                <li>Dominio: aremko.cl</li>
                <li>Servidor: SendGrid</li>
                <li>Estado: Funcionando</li>
            </ul>
            <p>--<br>Sistema Aremko</p>
            """,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email_destino],
            fail_silently=False
        )

        if result:
            print(f"\n✅ Correo enviado exitosamente a {email_destino}")
            print("Revisa tu bandeja de entrada (y carpeta de spam)")
            return True
        else:
            print(f"\n❌ El correo no se pudo enviar")
            return False

    except Exception as e:
        print(f"\n❌ ERROR al enviar correo: {str(e)}")
        print("\nPosibles causas:")
        print("1. SendGrid API Key inválida o expirada")
        print("2. Cuenta de SendGrid suspendida o con límite excedido")
        print("3. Dominio no verificado en SendGrid")
        print("4. Problemas de conectividad")
        return False

if __name__ == "__main__":
    # Verificar si hay archivo .env
    env_file = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_file):
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ Archivo .env cargado")
    else:
        print("⚠️  No se encontró archivo .env - usando variables del sistema")

    test_sendgrid_connection()