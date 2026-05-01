#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script rápido para probar email con SendGrid
Ejecutar: python test_email_quick.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.mail import send_mail
from django.conf import settings

print("\n" + "="*60)
print("DIAGNÓSTICO RÁPIDO DE EMAIL")
print("="*60)

# 1. Mostrar configuración
print("\n📋 CONFIGURACIÓN:")
print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")

# 2. Verificar API Key
sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
if sendgrid_key:
    masked = sendgrid_key[:10] + "..." + sendgrid_key[-10:]
    print(f"   SENDGRID_API_KEY: {masked}")
else:
    print("   ❌ SENDGRID_API_KEY no encontrada")

# 3. Enviar email de prueba
print("\n📧 ENVIANDO EMAIL DE PRUEBA...")
print("   De: aremkospa@gmail.com")
print("   Para: ecolonco@gmail.com")

try:
    result = send_mail(
        subject='✅ Prueba SendGrid - Aremko',
        message='Este es un email de prueba.',
        from_email='aremkospa@gmail.com',
        recipient_list=['ecolonco@gmail.com'],
        fail_silently=False,
    )

    print("\n" + "="*60)
    print("✅ EMAIL ENVIADO EXITOSAMENTE")
    print("="*60)
    print(f"\n   📬 Revisa tu inbox: ecolonco@gmail.com")
    print("   📁 Si no lo ves, revisa Spam/Promociones")
    print()

except Exception as e:
    print("\n" + "="*60)
    print("❌ ERROR AL ENVIAR EMAIL")
    print("="*60)
    print(f"\n   {str(e)}")
    print()
    sys.exit(1)
