#!/usr/bin/env python
"""
Test directo de la vista sin pasar por HTTP
Esto nos dirá si la vista funciona cuando Django la procesa
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from ventas.views_comandas_cliente import comanda_cliente_menu

print("=" * 70)
print("TEST DIRECTO DE VISTA (SIN HTTP)")
print("=" * 70)
print()

token = 'ocWz6uG0AoFe17sE3s18-i2Ie7SkzwSyi43VkhBWN6k'

print(f"1. Token a probar: {token[:30]}...")
print()

# Verificar que la comanda existe
print("2. Verificando que la comanda existe...")
from ventas.models import Comanda
try:
    comanda = Comanda.objects.get(token_acceso=token)
    print(f"   ✅ Comanda encontrada: #{comanda.id}")
    print(f"   Estado: {comanda.estado}")
    print(f"   Link válido: {comanda.es_link_valido()}")
except Comanda.DoesNotExist:
    print(f"   ❌ Comanda NO encontrada con ese token")
    sys.exit(1)

print()

# Crear request falso y llamar la vista directamente
print("3. Llamando vista directamente (sin HTTP)...")
factory = RequestFactory()
request = factory.get(f'/ventas/comanda-cliente/{token}/')

try:
    response = comanda_cliente_menu(request, token)
    print(f"   ✅ Vista ejecutada exitosamente")
    print(f"   Status code: {response.status_code}")
    print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")

    if response.status_code == 200:
        content = response.content.decode('utf-8')
        print(f"   Tamaño respuesta: {len(content)} bytes")

        # Buscar elementos clave en el HTML
        if '<title>' in content:
            title_start = content.find('<title>') + 7
            title_end = content.find('</title>')
            title = content[title_start:title_end]
            print(f"   Título: {title}")

        if 'Aremko Spa' in content:
            print(f"   ✅ Contiene 'Aremko Spa'")

        if 'Menú de Productos' in content:
            print(f"   ✅ Contiene 'Menú de Productos'")

    elif response.status_code == 404:
        print(f"   ⚠️ Vista retorna 404")
    else:
        print(f"   ⚠️ Status code inesperado: {response.status_code}")

except Exception as e:
    print(f"   ❌ Error al ejecutar vista: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print()

# Ahora probar con la URL completa a través del test client
print("4. Probando con TestClient de Django (simula HTTP completo)...")
from django.test import Client

client = Client()
response = client.get(f'/ventas/comanda-cliente/{token}/')

print(f"   Status code: {response.status_code}")
print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")

if response.status_code == 200:
    print(f"   ✅ TestClient retorna 200 OK")
elif response.status_code == 404:
    print(f"   ❌ TestClient retorna 404 Not Found")
    print(f"   Esto indica un problema con el URLconf en runtime")
else:
    print(f"   ⚠️ Status inesperado: {response.status_code}")

print()

# Verificar configuración de URLs en runtime
print("5. Verificando configuración de URLs en runtime...")
from django.conf import settings
print(f"   ROOT_URLCONF: {settings.ROOT_URLCONF}")
print(f"   DEBUG: {settings.DEBUG}")
print(f"   ALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")

print()

# Verificar si hay middleware que pueda estar bloqueando
print("6. Verificando middleware...")
from django.conf import settings
print(f"   Total middleware: {len(settings.MIDDLEWARE)}")
for i, mw in enumerate(settings.MIDDLEWARE, 1):
    print(f"   {i}. {mw}")

print()

# Intentar hacer una petición con el host correcto
print("7. Probando con HTTP_HOST correcto...")
response = client.get(
    f'/ventas/comanda-cliente/{token}/',
    HTTP_HOST='aremko-booking-system.onrender.com'
)
print(f"   Status code: {response.status_code}")

if response.status_code == 200:
    print(f"   ✅ Con HTTP_HOST correcto funciona!")
elif response.status_code == 404:
    print(f"   ❌ Sigue retornando 404 incluso con HTTP_HOST")

print()
print("=" * 70)
print("TEST COMPLETADO")
print("=" * 70)
print()

if response.status_code == 200:
    print("✅ La vista funciona correctamente en Django TestClient")
    print("   El problema debe estar en Gunicorn o en el proxy de Render")
else:
    print("❌ La vista no funciona ni en TestClient")
    print("   Hay un problema más profundo con la configuración")

print()
