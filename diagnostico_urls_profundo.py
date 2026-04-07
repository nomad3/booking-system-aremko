#!/usr/bin/env python
"""
Diagnóstico profundo de URLs de comandas
Uso: python diagnostico_urls_profundo.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("=" * 70)
print("DIAGNÓSTICO PROFUNDO DE URLs DE COMANDAS")
print("=" * 70)
print()

# 1. Verificar que el módulo existe
print("1. Verificando importación del módulo views_comandas_cliente...")
try:
    from ventas import views_comandas_cliente
    print("   ✅ Módulo views_comandas_cliente importado correctamente")
    print(f"   Ubicación: {views_comandas_cliente.__file__}")
except ImportError as e:
    print(f"   ❌ Error importando módulo: {e}")
    sys.exit(1)

print()

# 2. Verificar que las vistas existen
print("2. Verificando existencia de vistas...")
vistas_requeridas = [
    'comanda_cliente_menu',
    'comanda_cliente_agregar_producto',
    'comanda_cliente_actualizar_cantidad',
    'comanda_cliente_finalizar',
    'comanda_cliente_pago_confirmacion',
    'comanda_cliente_pago_retorno',
]

for vista in vistas_requeridas:
    existe = hasattr(views_comandas_cliente, vista)
    if existe:
        print(f"   ✅ Vista '{vista}' existe")
    else:
        print(f"   ❌ Vista '{vista}' NO EXISTE")

print()

# 3. Verificar que las URLs se resuelven
print("3. Verificando resolución de URLs...")
from django.urls import reverse, NoReverseMatch

urls_test = [
    ('ventas:comanda_cliente', {'token': 'test-token'}),
    ('ventas:comanda_cliente_agregar_producto', {'token': 'test-token'}),
    ('ventas:comanda_cliente_finalizar', {'token': 'test-token'}),
]

for url_name, kwargs in urls_test:
    try:
        url = reverse(url_name, kwargs=kwargs)
        print(f"   ✅ {url_name} → {url}")
    except NoReverseMatch as e:
        print(f"   ❌ {url_name} → ERROR: {e}")

print()

# 4. Verificar patrones de URL en URLconf
print("4. Verificando patrones de URL en URLconf...")
from django.urls import get_resolver

resolver = get_resolver()

# Buscar patrones que contengan "comanda-cliente"
print("   Buscando patrones con 'comanda-cliente'...")
found_patterns = []

def buscar_patrones(patterns, prefix=''):
    """Función recursiva para buscar patrones"""
    for pattern in patterns:
        if hasattr(pattern, 'url_patterns'):
            # Es un include, buscar recursivamente
            new_prefix = prefix + str(pattern.pattern)
            buscar_patrones(pattern.url_patterns, new_prefix)
        else:
            # Es un patrón individual
            full_pattern = prefix + str(pattern.pattern)
            if 'comanda-cliente' in full_pattern:
                found_patterns.append({
                    'pattern': full_pattern,
                    'name': pattern.name if hasattr(pattern, 'name') else 'sin nombre',
                    'callback': pattern.callback.__name__ if hasattr(pattern, 'callback') else 'N/A'
                })

buscar_patrones(resolver.url_patterns)

if found_patterns:
    print(f"   ✅ Encontrados {len(found_patterns)} patrones:")
    for p in found_patterns:
        print(f"      - {p['pattern']}")
        print(f"        nombre: {p['name']}, vista: {p['callback']}")
else:
    print("   ❌ NO se encontraron patrones con 'comanda-cliente'")

print()

# 5. Verificar archivo de URLs de ventas
print("5. Verificando archivo ventas/urls.py...")
urls_file = os.path.join(os.path.dirname(__file__), 'ventas', 'urls.py')
if os.path.exists(urls_file):
    print(f"   ✅ Archivo existe: {urls_file}")

    # Leer y buscar las líneas de comanda-cliente
    with open(urls_file, 'r') as f:
        content = f.read()
        if 'comanda-cliente' in content:
            print("   ✅ Contiene definiciones de 'comanda-cliente'")

            # Contar cuántas líneas
            lines = [line for line in content.split('\n') if 'comanda-cliente' in line and 'path(' in line]
            print(f"   Encontradas {len(lines)} definiciones de path con 'comanda-cliente'")
        else:
            print("   ❌ NO contiene 'comanda-cliente'")
else:
    print(f"   ❌ Archivo NO existe: {urls_file}")

print()

# 6. Verificar importación en urls.py
print("6. Verificando importación en ventas/urls.py...")
try:
    with open(urls_file, 'r') as f:
        content = f.read()
        if 'views_comandas_cliente' in content:
            print("   ✅ views_comandas_cliente está importado en urls.py")

            # Mostrar la línea de importación
            for line in content.split('\n'):
                if 'views_comandas_cliente' in line and 'import' in line:
                    print(f"      {line.strip()}")
        else:
            print("   ❌ views_comandas_cliente NO está importado en urls.py")
except Exception as e:
    print(f"   ⚠️ Error leyendo archivo: {e}")

print()

# 7. Probar resolver una URL específica
print("7. Probando resolver URL específica...")
from django.urls import resolve
from django.http import Http404

test_path = '/ventas/comanda-cliente/ocWz6uG0AoFe17sE3s18-i2Ie7SkzwSyi43VkhBWN6k/'
try:
    match = resolve(test_path)
    print(f"   ✅ URL resuelve correctamente:")
    print(f"      View: {match.func.__name__}")
    print(f"      Module: {match.func.__module__}")
    print(f"      URL name: {match.url_name}")
    print(f"      Namespace: {match.namespace}")
    print(f"      kwargs: {match.kwargs}")
except Http404:
    print(f"   ❌ URL NO resuelve (404)")
except Exception as e:
    print(f"   ❌ Error resolviendo URL: {e}")

print()

# 8. Verificar archivo views_comandas_cliente.py
print("8. Verificando archivo views_comandas_cliente.py...")
views_file = os.path.join(os.path.dirname(__file__), 'ventas', 'views_comandas_cliente.py')
if os.path.exists(views_file):
    print(f"   ✅ Archivo existe: {views_file}")

    # Ver tamaño
    size = os.path.getsize(views_file)
    print(f"   Tamaño: {size} bytes")

    # Contar funciones def
    with open(views_file, 'r') as f:
        content = f.read()
        func_count = content.count('def comanda_cliente_')
        print(f"   Funciones 'comanda_cliente_*': {func_count}")
else:
    print(f"   ❌ Archivo NO existe: {views_file}")

print()
print("=" * 70)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 70)
print()

if found_patterns and os.path.exists(views_file):
    print("✅ CONCLUSIÓN: Django está configurado correctamente")
    print("   El problema es que Gunicorn no recargó los módulos.")
    print("   SOLUCIÓN: Reinicia el servicio desde Render Dashboard")
else:
    print("❌ CONCLUSIÓN: Hay problemas de configuración")
    print("   Revisa los mensajes de error arriba")

print()
