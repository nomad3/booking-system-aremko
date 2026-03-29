#!/usr/bin/env python
"""
Script simplificado para diagnosticar SendGrid via SMTP
No requiere librerías adicionales - Solo usa módulos estándar de Python
Ejecutar en shell de Render: python scripts/diagnostics/test_sendgrid_simple.py
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

def print_section(title):
    """Imprime un separador de sección"""
    print("\n" + "="*60)
    print(f" {title}")
    print("="*60)

def test_sendgrid():
    print("="*60)
    print(" DIAGNÓSTICO RÁPIDO DE SENDGRID")
    print("="*60)

    # Buscar API key en diferentes variables
    api_key = (
        os.getenv('SENDGRID_API_KEY') or
        os.getenv('SENDGRID_API_KEY_ID') or
        os.getenv('EMAIL_HOST_PASSWORD') or
        ''
    )

    email_host = os.getenv('EMAIL_HOST', 'smtp.sendgrid.net')
    email_port = int(os.getenv('EMAIL_PORT', '587'))
    email_user = os.getenv('EMAIL_HOST_USER', 'apikey')
    from_email = os.getenv('DEFAULT_FROM_EMAIL', 'ventas@aremko.cl')

    print(f"\n📧 CONFIGURACIÓN DETECTADA:")
    print(f"Host: {email_host}")
    print(f"Puerto: {email_port}")
    print(f"Usuario: {email_user}")
    print(f"From: {from_email}")
    print(f"API Key: {'✅ Configurada' if api_key else '❌ NO ENCONTRADA'} ({len(api_key)} chars)")

    if not api_key:
        print("\n❌ ERROR: No se encontró API Key de SendGrid")
        print("\nVariables revisadas:")
        print("- SENDGRID_API_KEY")
        print("- SENDGRID_API_KEY_ID")
        print("- EMAIL_HOST_PASSWORD")
        print("\nConfigura una de estas variables en Render con tu API Key de SendGrid")
        return False

    # Si es SendGrid, el usuario siempre es 'apikey'
    if 'sendgrid' in email_host.lower():
        email_user = 'apikey'
        print("\n✅ Detectado SendGrid - usando usuario 'apikey'")

    # Test de conexión SMTP
    print("\n🔌 PROBANDO CONEXIÓN SMTP...")
    try:
        server = smtplib.SMTP(email_host, email_port)
        print("✅ Conectado al servidor")

        print("🔐 Iniciando TLS...")
        server.starttls()
        print("✅ TLS activado")

        print(f"🔑 Autenticando como '{email_user}'...")
        server.login(email_user, api_key)
        print("✅ Autenticación exitosa!")

        server.quit()

        # Ofrecer enviar correo de prueba
        print("\n" + "="*60)
        test_email = input("📮 Ingresa un correo para enviar prueba (o Enter para salir): ").strip()

        if test_email:
            print(f"\n📤 Enviando correo de prueba a {test_email}...")

            msg = MIMEMultipart()
            msg['From'] = from_email
            msg['To'] = test_email
            msg['Subject'] = f"Prueba SendGrid - {datetime.now().strftime('%H:%M:%S')}"

            body = f"""
Hola!

Este es un correo de prueba desde SendGrid.

✅ Si recibes este mensaje, la configuración está funcionando correctamente.

Configuración utilizada:
- Servidor: {email_host}
- Puerto: {email_port}
- Remitente: {from_email}
- Fecha: {datetime.now()}

Saludos,
Sistema Aremko
            """
            msg.attach(MIMEText(body, 'plain'))

            try:
                server = smtplib.SMTP(email_host, email_port)
                server.starttls()
                server.login(email_user, api_key)
                server.send_message(msg)
                server.quit()

                print("✅ Correo enviado exitosamente!")
                print("   Revisa la bandeja (y SPAM)")

            except Exception as e:
                print(f"❌ Error al enviar: {e}")

        return True

    except smtplib.SMTPAuthenticationError as e:
        print(f"\n❌ Error de autenticación: {e}")
        print("\nPOSIBLES CAUSAS:")
        print("1. API Key incorrecta o expirada")
        print("2. API Key sin permisos de envío")
        print("3. Usuario incorrecto (debe ser 'apikey' para SendGrid)")
        print("4. Cuenta de SendGrid suspendida o con límites excedidos")

    except smtplib.SMTPException as e:
        print(f"\n❌ Error SMTP: {e}")

    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")

    return False

if __name__ == "__main__":
    print("\n🚀 INICIANDO DIAGNÓSTICO DE SENDGRID\n")

    success = test_sendgrid()

    print("\n" + "="*60)
    if success:
        print("✅ RESULTADO: SendGrid funciona correctamente")
        print("\nSi la app no envía correos, verifica:")
        print("1. Que Django use las mismas variables")
        print("2. Los logs de errores en Render")
        print("3. El Activity Feed en SendGrid")
    else:
        print("❌ RESULTADO: Problemas con SendGrid")
        print("\nACCIONES RECOMENDADAS:")
        print("1. Verifica tu API Key en SendGrid Dashboard")
        print("2. Genera una nueva API Key con permisos 'Mail Send'")
        print("3. Actualiza la variable en Render")
        print("4. Verifica el dominio en Sender Authentication")

    print("\n📊 SendGrid Dashboard: https://app.sendgrid.com/")
    print("="*60)