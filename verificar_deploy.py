#!/usr/bin/env python
"""
Verifica que el código más reciente esté desplegado
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=" * 70)
print("VERIFICACIÓN DE DEPLOY")
print("=" * 70)
print()

# 1. Verificar que las URLs bajo /api/comanda/ existen
print("1. Verificando URLs bajo /api/comanda/...")
from django.urls import reverse, NoReverseMatch

try:
    url = reverse('ventas:comanda_cliente_api', kwargs={'token': 'test-token'})
    print(f"   ✅ URL /api/comanda/ existe: {url}")
    codigo_nuevo = True
except NoReverseMatch:
    print(f"   ❌ URL /api/comanda/ NO existe")
    codigo_nuevo = False

print()

# 2. Ver qué versión del método obtener_url_cliente tenemos
print("2. Verificando método obtener_url_cliente()...")
from ventas.models import Comanda
import inspect

source = inspect.getsource(Comanda.obtener_url_cliente)
if 'comanda_cliente_api' in source:
    print("   ✅ Método usa 'comanda_cliente_api' (código nuevo)")
elif 'comanda_cliente_short' in source:
    print("   ⚠️ Método usa 'comanda_cliente_short' (código intermedio)")
elif 'use_short_url' in source:
    print("   ⚠️ Método tiene parámetro 'use_short_url' (código intermedio)")
else:
    print("   ❌ Método usa código viejo")

print()

# 3. Listar todas las URLs que contienen 'comanda'
print("3. URLs disponibles con 'comanda'...")
from django.urls import get_resolver

resolver = get_resolver()

def buscar_urls(patterns, prefix=''):
    urls = []
    for pattern in patterns:
        if hasattr(pattern, 'url_patterns'):
            urls.extend(buscar_urls(pattern.url_patterns, prefix + str(pattern.pattern)))
        else:
            full_pattern = prefix + str(pattern.pattern)
            if 'comanda' in full_pattern.lower():
                name = f"{pattern.namespace}:{pattern.name}" if hasattr(pattern, 'namespace') and pattern.namespace else (pattern.name if hasattr(pattern, 'name') else 'sin nombre')
                urls.append((full_pattern, name))
    return urls

urls = buscar_urls(resolver.url_patterns)
for url, name in urls:
    print(f"   - {url} ({name})")

print()

# 4. Probar generar URL de comanda real
print("4. Probando generar URL de comanda #39...")
try:
    comanda = Comanda.objects.get(id=39)
    url = comanda.obtener_url_cliente()
    print(f"   ✅ URL generada: {url}")

    if '/api/comanda/' in url:
        print(f"   ✅ Usa ruta correcta (/api/comanda/)")
    else:
        print(f"   ❌ NO usa ruta /api/comanda/")

except Exception as e:
    print(f"   ❌ Error: {e}")

print()
print("=" * 70)

if codigo_nuevo:
    print("✅ CÓDIGO NUEVO DESPLEGADO CORRECTAMENTE")
    print()
    print("Prueba esta URL en el navegador:")
    print(f"   https://aremko-booking-system.onrender.com/ventas/api/comanda/ocWz6uG0AoFe17sE3s18-i2Ie7SkzwSyi43VkhBWN6k/")
else:
    print("❌ CÓDIGO VIEJO - RENDER NO DESPLEGÓ")
    print()
    print("Acciones:")
    print("1. Verifica en Render Dashboard que el deploy terminó")
    print("2. Revisa los logs de build")
    print("3. Intenta hacer Manual Deploy nuevamente")

print("=" * 70)
print()
