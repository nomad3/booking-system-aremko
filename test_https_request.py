#!/usr/bin/env python
"""
Test con HTTPS simulado para ver si el problema es SSL redirect
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import Client
from django.conf import settings

print("=" * 70)
print("TEST CON HTTPS SIMULADO")
print("=" * 70)
print()

token = 'ocWz6uG0AoFe17sE3s18-i2Ie7SkzwSyi43VkhBWN6k'
path = f'/ventas/comanda-cliente/{token}/'

print("Configuración actual:")
print(f"  SECURE_SSL_REDIRECT: {settings.SECURE_SSL_REDIRECT}")
print(f"  DEBUG: {settings.DEBUG}")
print(f"  ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print()

# Test 1: HTTP sin host
print("1. Test con HTTP, sin host:")
client = Client()
response = client.get(path)
print(f"   Status: {response.status_code}")
print()

# Test 2: HTTP con host correcto
print("2. Test con HTTP, host=aremko-booking-system.onrender.com:")
response = client.get(
    path,
    HTTP_HOST='aremko-booking-system.onrender.com'
)
print(f"   Status: {response.status_code}")
if response.status_code == 301:
    print(f"   Redirect a: {response.get('Location', 'N/A')}")
print()

# Test 3: HTTPS simulado (el correcto)
print("3. Test con HTTPS simulado (HTTP_X_FORWARDED_PROTO=https):")
response = client.get(
    path,
    HTTP_HOST='aremko-booking-system.onrender.com',
    HTTP_X_FORWARDED_PROTO='https',
    secure=True
)
print(f"   Status: {response.status_code}")

if response.status_code == 200:
    print(f"   ✅ FUNCIONA CON HTTPS!")
    content = response.content.decode('utf-8')
    print(f"   Tamaño: {len(content)} bytes")
    if 'Aremko Spa' in content:
        print(f"   ✅ Contiene 'Aremko Spa'")
elif response.status_code == 301:
    print(f"   Redirect a: {response.get('Location', 'N/A')}")
elif response.status_code == 404:
    print(f"   ❌ Sigue retornando 404")
print()

# Test 4: Probar con diferentes variantes del host
print("4. Probando variantes del hostname:")
hostnames = [
    'aremko-booking-system.onrender.com',
    'aremko-booking-systemprod.onrender.com',
    'www.aremko.cl',
    'aremko.cl',
]

for hostname in hostnames:
    response = client.get(
        path,
        HTTP_HOST=hostname,
        HTTP_X_FORWARDED_PROTO='https',
        secure=True
    )
    status_symbol = "✅" if response.status_code == 200 else "❌"
    print(f"   {status_symbol} {hostname}: {response.status_code}")

print()

# Test 5: Verificar si el problema es con la URL o con ALLOWED_HOSTS
print("5. Verificando si 'aremko-booking-system.onrender.com' está permitido:")
test_host = 'aremko-booking-system.onrender.com'

# Verificar manualmente
from django.http import HttpRequest
request = HttpRequest()
request.META['HTTP_HOST'] = test_host

from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpRequest

# Verificar con el validador de Django
allowed = False
for pattern in settings.ALLOWED_HOSTS:
    if pattern == test_host:
        allowed = True
        break
    elif pattern.startswith('.') and test_host.endswith(pattern[1:]):
        allowed = True
        break
    elif pattern == '*':
        allowed = True
        break

if allowed:
    print(f"   ✅ {test_host} está permitido en ALLOWED_HOSTS")
else:
    print(f"   ❌ {test_host} NO está permitido en ALLOWED_HOSTS")
    print(f"   ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")

print()
print("=" * 70)
print("CONCLUSIÓN")
print("=" * 70)
print()

if response.status_code == 200:
    print("✅ La URL funciona correctamente con HTTPS simulado")
    print()
    print("El problema es que las peticiones HTTP reales están:")
    print("1. Siendo bloqueadas por Render antes de llegar a Gunicorn")
    print("2. No incluyendo el header X-Forwarded-Proto correctamente")
    print("3. Teniendo algún problema con el proxy de Render")
    print()
    print("SOLUCIÓN:")
    print("- Verifica la configuración del servicio en Render")
    print("- Asegúrate que el puerto esté configurado correctamente")
    print("- Revisa los logs de Render cuando accedes a la URL")
else:
    print(f"❌ Incluso con HTTPS simulado falla: {response.status_code}")
    print()
    print("Esto indica un problema de configuración más profundo")

print()
