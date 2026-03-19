#!/usr/bin/env python
"""
Script para verificar el estado de la cuenta SendGrid
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.conf import settings
import requests

print("=== VERIFICACIÓN DE SENDGRID ===\n")

# Verificar configuración
api_key = os.getenv('SENDGRID_API_KEY', '')
if not api_key:
    print("❌ No se encontró SENDGRID_API_KEY en las variables de entorno")
    exit(1)

print(f"✅ API Key encontrada: {api_key[:10]}...")

# Verificar estado de la cuenta
headers = {
    'Authorization': f'Bearer {api_key}',
    'Content-Type': 'application/json'
}

# 1. Verificar autenticación
print("\n1. Verificando autenticación...")
response = requests.get('https://api.sendgrid.com/v3/user/account', headers=headers)
if response.status_code == 200:
    print("✅ Autenticación exitosa")
    account_data = response.json()
    print(f"   Tipo de cuenta: {account_data.get('type', 'N/A')}")
else:
    print(f"❌ Error de autenticación: {response.status_code}")
    print(f"   Mensaje: {response.text}")

# 2. Verificar límites y uso
print("\n2. Verificando límites de envío...")
response = requests.get('https://api.sendgrid.com/v3/user/credits', headers=headers)
if response.status_code == 200:
    credits = response.json()
    print(f"✅ Créditos disponibles: {credits.get('remain', 'N/A')}")
    print(f"   Total: {credits.get('total', 'N/A')}")
    print(f"   Usados: {credits.get('used', 'N/A')}")
else:
    print(f"⚠️  No se pudo verificar créditos: {response.status_code}")

# 3. Verificar estado del plan
print("\n3. Verificando plan/billing...")
response = requests.get('https://api.sendgrid.com/v3/user/billing', headers=headers)
if response.status_code == 200:
    print("✅ Información de billing accesible")
else:
    print(f"⚠️  No se pudo acceder a billing: {response.status_code}")

# 4. Intentar enviar un email de prueba
print("\n4. Intentando enviar email de prueba...")
from django.core.mail import send_mail

try:
    result = send_mail(
        'Test SendGrid - Verificación de Estado',
        'Este es un email de prueba para verificar el estado de SendGrid.',
        settings.DEFAULT_FROM_EMAIL,
        ['test@example.com'],  # Email de prueba
        fail_silently=False,
    )
    print(f"✅ Email enviado exitosamente: {result}")
except Exception as e:
    print(f"❌ Error al enviar email: {str(e)}")
    print(f"   Tipo de error: {type(e).__name__}")

print("\n=== FIN DE VERIFICACIÓN ===")