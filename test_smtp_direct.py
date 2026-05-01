#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test de envío directo SMTP (igual al que funcionó antes)
"""

import os
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

print("\n" + "="*60)
print("TEST SMTP DIRECTO (igual al que funcionó antes)")
print("="*60)

# Obtener API Key
sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
if not sendgrid_key:
    print("\n❌ SENDGRID_API_KEY no encontrada")
    sys.exit(1)

print(f"\n🔑 API Key: {sendgrid_key[:10]}...{sendgrid_key[-10:]}")

# Datos del email
from_email = 'aremkospa@gmail.com'
to_email = input("\n📧 Email de destino (presiona Enter para ecolonco@gmail.com): ").strip()
if not to_email:
    to_email = 'ecolonco@gmail.com'

print(f"\n   From: {from_email}")
print(f"   To: {to_email}")

confirm = input("\n¿Continuar? (s/n): ").strip().lower()
if confirm != 's':
    print("\n❌ Cancelado")
    sys.exit(0)

print("\n📤 Conectando a SendGrid...")

try:
    # Conectar
    server = smtplib.SMTP('smtp.sendgrid.net', 587, timeout=30)
    print("   ✅ Conectado")

    # STARTTLS
    print("   🔒 Iniciando TLS...")
    server.starttls()
    print("   ✅ TLS activado")

    # Autenticar
    print("   🔑 Autenticando...")
    server.login('apikey', sendgrid_key)
    print("   ✅ Autenticado")

    # Crear mensaje
    msg = MIMEMultipart('alternative')
    msg['Subject'] = '✅ Test SMTP Directo - Aremko'
    msg['From'] = from_email
    msg['To'] = to_email

    # Texto plano
    text = 'Este es un test de envío SMTP directo desde Aremko.'

    # HTML
    html = """
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px;">
        <h2 style="color: #2c5f2d;">✅ Test SMTP Directo</h2>
        <p>Este email se envió usando <strong>SMTP directo</strong> (sin Django).</p>
        <p>Si recibes este mensaje, significa que la conexión con SendGrid funciona correctamente.</p>
        <hr>
        <p style="font-size: 12px; color: #666;">
            Aremko Spa Boutique<br>
            Puerto Varas, Chile
        </p>
    </body>
    </html>
    """

    # Adjuntar partes
    part1 = MIMEText(text, 'plain')
    part2 = MIMEText(html, 'html')
    msg.attach(part1)
    msg.attach(part2)

    # Enviar
    print("   📨 Enviando mensaje...")
    server.send_message(msg)
    print("   ✅ Mensaje enviado")

    # Cerrar
    server.quit()

    print("\n" + "="*60)
    print("✅ EMAIL ENVIADO EXITOSAMENTE")
    print("="*60)
    print(f"\n   📬 Revisa: {to_email}")
    print()

except smtplib.SMTPAuthenticationError as e:
    print("\n" + "="*60)
    print("❌ ERROR DE AUTENTICACIÓN")
    print("="*60)
    print(f"\n   {str(e)}")
    print("\n   La API Key no es válida o no tiene permisos.")
    print()

except smtplib.SMTPSenderRefused as e:
    print("\n" + "="*60)
    print("❌ SENDER RECHAZADO")
    print("="*60)
    print(f"\n   {str(e)}")
    print("\n   El email 'aremkospa@gmail.com' NO está verificado en SendGrid.")
    print()

except Exception as e:
    print("\n" + "="*60)
    print("❌ ERROR")
    print("="*60)
    print(f"\n   Tipo: {type(e).__name__}")
    print(f"   Error: {str(e)}")
    print()
