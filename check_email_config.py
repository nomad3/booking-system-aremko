#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Script para verificar configuración de email
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings

print("\n" + "="*60)
print("CONFIGURACIÓN DE EMAIL")
print("="*60)

print("\n📧 CONFIGURACIÓN DJANGO:")
print(f"   EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
print(f"   EMAIL_HOST: {settings.EMAIL_HOST}")
print(f"   EMAIL_PORT: {settings.EMAIL_PORT}")
print(f"   EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
print(f"   EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")

# DEFAULT_FROM_EMAIL
default_from = getattr(settings, 'DEFAULT_FROM_EMAIL', 'No configurado')
print(f"   DEFAULT_FROM_EMAIL: {default_from}")

# VENTAS_FROM_EMAIL (si existe)
ventas_from = getattr(settings, 'VENTAS_FROM_EMAIL', 'No configurado')
if ventas_from != 'No configurado':
    print(f"   VENTAS_FROM_EMAIL: {ventas_from}")

print("\n🔑 SENDGRID:")
sendgrid_key = os.getenv('SENDGRID_API_KEY', '')
if sendgrid_key:
    masked = sendgrid_key[:10] + "..." + sendgrid_key[-10:]
    print(f"   SENDGRID_API_KEY: {masked}")
    print(f"   Longitud: {len(sendgrid_key)} caracteres")
else:
    print("   ❌ SENDGRID_API_KEY no encontrada")

print("\n⚠️  VERIFICACIÓN:")
if default_from == 'aremkospa@gmail.com':
    print("   ✅ DEFAULT_FROM_EMAIL coincide con el sender verificado en SendGrid")
else:
    print(f"   ❌ DEFAULT_FROM_EMAIL es '{default_from}'")
    print("   ❌ Pero el sender verificado en SendGrid es: aremkospa@gmail.com")
    print("   ⚠️  ESTO CAUSARÁ ERRORES DE ENVÍO!")
    print("\n   SOLUCIÓN:")
    print("   Agrega esta variable en Render Environment:")
    print("   DEFAULT_FROM_EMAIL=aremkospa@gmail.com")

print("\n" + "="*60)
print()
