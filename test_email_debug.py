#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script de diagnóstico detallado para SendGrid
"""

import os
import sys
import django
import smtplib
import logging

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

print("\n" + "="*60)
print("DIAGNÓSTICO DETALLADO DE SENDGRID")
print("="*60)

# 1. Verificar variables
print("\n📋 VARIABLES DE ENTORNO:")
sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
print(f"   SENDGRID_API_KEY presente: {'✅ Sí' if sendgrid_key else '❌ No'}")
if sendgrid_key:
    print(f"   Longitud: {len(sendgrid_key)} caracteres")
    print(f"   Comienza con: {sendgrid_key[:10]}...")
    print(f"   Termina con: ...{sendgrid_key[-10:]}")

# 2. Verificar sender
print("\n📧 SENDER IDENTITY:")
print(f"   From: aremkospa@gmail.com")
print("   ⚠️  IMPORTANTE: Este email debe estar verificado en SendGrid")

# 3. Test SMTP directo
print("\n🔍 PROBANDO CONEXIÓN SMTP DIRECTA...")
print(f"   Host: smtp.sendgrid.net")
print(f"   Port: 587")
print(f"   Usuario: apikey")

try:
    # Intentar conexión SMTP directa con más detalle
    import smtplib
    from email.mime.text import MIMEText

    print("\n   Conectando a SendGrid...")
    server = smtplib.SMTP('smtp.sendgrid.net', 587, timeout=30)
    server.set_debuglevel(1)  # Mostrar debug completo

    print("   Iniciando STARTTLS...")
    server.starttls()

    print("   Autenticando...")
    server.login('apikey', sendgrid_key)

    print("   ✅ Conexión exitosa!")

    print("\n   Enviando email...")
    msg = MIMEText('Este es un email de prueba desde Aremko')
    msg['Subject'] = '✅ Prueba SendGrid - Aremko'
    msg['From'] = 'aremkospa@gmail.com'
    msg['To'] = 'ecolonco@gmail.com'

    server.send_message(msg)
    server.quit()

    print("\n" + "="*60)
    print("✅ EMAIL ENVIADO EXITOSAMENTE VÍA SMTP DIRECTO")
    print("="*60)
    print("\n   📬 Revisa: ecolonco@gmail.com")
    print()

except smtplib.SMTPAuthenticationError as e:
    print("\n" + "="*60)
    print("❌ ERROR DE AUTENTICACIÓN")
    print("="*60)
    print(f"\n   {str(e)}")
    print("\n   Posibles causas:")
    print("   1. API Key incorrecta")
    print("   2. API Key sin permisos de 'Mail Send'")
    print("   3. Espacios o caracteres extra en la API Key")
    print()

except smtplib.SMTPSenderRefused as e:
    print("\n" + "="*60)
    print("❌ SENDER RECHAZADO")
    print("="*60)
    print(f"\n   {str(e)}")
    print("\n   Causa más probable:")
    print("   ⚠️  El email 'aremkospa@gmail.com' NO está verificado en SendGrid")
    print("\n   Solución:")
    print("   1. Ve a SendGrid → Settings → Sender Authentication")
    print("   2. Verifica que 'aremkospa@gmail.com' esté verificado (verde)")
    print("   3. Si no está, reenvía el email de verificación")
    print()

except Exception as e:
    print("\n" + "="*60)
    print("❌ ERROR DE CONEXIÓN")
    print("="*60)
    print(f"\n   Tipo: {type(e).__name__}")
    print(f"   Error: {str(e)}")
    print()

    if "Connection unexpectedly closed" in str(e):
        print("   Causas posibles:")
        print("   1. Sender Identity no verificado en SendGrid")
        print("   2. API Key inválida o con caracteres extra")
        print("   3. Problema de red desde Render a SendGrid")
        print()
