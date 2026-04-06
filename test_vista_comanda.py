#!/usr/bin/env python
"""
Script para probar la vista de comanda directamente
Uso: python test_vista_comanda.py <token>
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from ventas.views_comandas_cliente import comanda_cliente_menu

if len(sys.argv) < 2:
    print("❌ Uso: python test_vista_comanda.py <token>")
    sys.exit(1)

token = sys.argv[1]

print("="*60)
print(f"PROBANDO VISTA CON TOKEN: {token[:20]}...")
print("="*60)
print()

factory = RequestFactory()
request = factory.get(f'/ventas/comanda-cliente/{token}/')

try:
    response = comanda_cliente_menu(request, token)
    print(f"✅ Vista ejecutada correctamente")
    print(f"   Status code: {response.status_code}")
    print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")

    if response.status_code == 200:
        print(f"   Template renderizado exitosamente")
        # Intentar ver si tiene contenido HTML
        content = response.content.decode('utf-8')
        if '<title>' in content:
            title_start = content.find('<title>') + 7
            title_end = content.find('</title>')
            title = content[title_start:title_end]
            print(f"   Título de la página: {title}")

        if 'Aremko Spa' in content:
            print(f"   ✅ Contenido contiene 'Aremko Spa'")

        print(f"   Tamaño del HTML: {len(content)} bytes")
    else:
        print(f"   ⚠️ Status code no es 200")

except Exception as e:
    print(f"❌ Error al ejecutar la vista:")
    print(f"   {type(e).__name__}: {e}")
    print()
    import traceback
    traceback.print_exc()

print()
print("="*60)
