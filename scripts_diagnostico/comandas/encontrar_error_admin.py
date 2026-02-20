#!/usr/bin/env python
"""
Script para encontrar el error exacto en el admin
Ejecutar con: python manage.py shell < encontrar_error_admin.py
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("\n" + "=" * 80)
print("BUSCANDO ERROR EN ADMIN")
print("=" * 80)
print()

# 1. Probar imports uno por uno
print("1. PROBANDO IMPORTS INDIVIDUALES")
print("-" * 40)

imports_to_test = [
    "from django.contrib import admin",
    "from ventas.models import *",
    "from control_gestion.views_comandas import *",
    "from ventas.admin import *",
]

for imp in imports_to_test:
    try:
        exec(imp)
        print(f"✓ {imp}")
    except Exception as e:
        print(f"✗ {imp}")
        print(f"  Error: {type(e).__name__}: {e}")

# 2. Probar carga de URLs
print("\n2. PROBANDO CARGA DE URLs")
print("-" * 40)

try:
    from django.urls import include, path
    from django.contrib import admin as admin_module

    # Simular la carga de URLs del admin
    admin_urls = admin_module.site.urls
    print("✓ URLs del admin cargadas correctamente")

except Exception as e:
    print(f"✗ Error cargando URLs del admin: {e}")
    import traceback
    traceback.print_exc()

# 3. Verificar el proyecto principal
print("\n3. VERIFICANDO CONFIGURACIÓN PRINCIPAL")
print("-" * 40)

try:
    from aremko_project import urls
    print("✓ URLs principales cargadas")
except Exception as e:
    print(f"✗ Error en URLs principales: {e}")
    import traceback
    traceback.print_exc()

# 4. Buscar el módulo problemático
print("\n4. RASTREANDO MÓDULO PROBLEMÁTICO")
print("-" * 40)

# Lista de módulos a verificar
modules_to_check = [
    'ventas.admin',
    'control_gestion.admin',
    'control_gestion.urls',
    'control_gestion.views',
    'control_gestion.views_comandas',
]

for module_name in modules_to_check:
    try:
        # Intentar importar el módulo
        module = __import__(module_name, fromlist=[''])
        print(f"✓ {module_name} cargado correctamente")

        # Si es un módulo admin, verificar registros
        if 'admin' in module_name:
            if hasattr(module, 'site'):
                print(f"  → Tiene {len(getattr(module.site, '_registry', {}))} modelos registrados")

    except ImportError as e:
        print(f"✗ ImportError en {module_name}: {e}")
    except Exception as e:
        print(f"✗ Error en {module_name}: {type(e).__name__}: {e}")
        if "total_items" in str(e) or "total_precio" in str(e):
            print("  → ERROR RELACIONADO CON PROPIEDADES DE COMANDA")

# 5. Verificar si es un problema de memoria/timeout
print("\n5. INFORMACIÓN DEL SISTEMA")
print("-" * 40)

import platform
print(f"Python: {platform.python_version()}")
print(f"Django: {django.VERSION}")

# Contar modelos registrados
try:
    from django.contrib.admin import site
    print(f"Modelos en admin: {len(site._registry)}")
except:
    print("No se puede acceder al registro del admin")

print("\n" + "=" * 80)
print("CONCLUSIÓN")
print("=" * 80)
print()
print("Si ves errores relacionados con 'total_items' o propiedades:")
print("→ El problema está en las propiedades del modelo Comanda")
print()
print("Si ves errores de importación:")
print("→ Hay un problema con las rutas o nombres de módulos")
print()
print("=" * 80)