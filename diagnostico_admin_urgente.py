#!/usr/bin/env python
"""
DIAGNÓSTICO URGENTE - Admin no funciona
Ejecutar con: python manage.py shell < diagnostico_admin_urgente.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

print("\n" + "=" * 80)
print("DIAGNÓSTICO URGENTE - ERROR EN ADMIN")
print("=" * 80)
print()

# 1. Verificar imports básicos
print("1. VERIFICANDO IMPORTS BÁSICOS")
print("-" * 40)

try:
    from django.contrib import admin
    print("✓ django.contrib.admin importado")
except Exception as e:
    print(f"✗ Error importando admin: {e}")

try:
    from ventas import admin as ventas_admin
    print("✓ ventas.admin importado")
except Exception as e:
    print(f"✗ Error importando ventas.admin: {e}")
    import traceback
    traceback.print_exc()

# 2. Verificar modelos
print("\n2. VERIFICANDO MODELOS")
print("-" * 40)

try:
    from ventas.models import Comanda
    print("✓ Modelo Comanda importado")

    # Verificar propiedades agregadas
    comanda_test = Comanda()
    propiedades = ['total_items', 'total_precio', 'lugar_entrega', 'es_urgente']

    for prop in propiedades:
        try:
            if hasattr(comanda_test, prop):
                print(f"✓ Propiedad '{prop}' existe")
            else:
                print(f"✗ Propiedad '{prop}' NO existe")
        except Exception as e:
            print(f"✗ Error verificando '{prop}': {e}")

except Exception as e:
    print(f"✗ Error con modelo Comanda: {e}")
    import traceback
    traceback.print_exc()

# 3. Verificar AdminSite
print("\n3. VERIFICANDO ADMIN SITE")
print("-" * 40)

try:
    from django.contrib.admin import site
    print(f"✓ Admin site existe")
    print(f"  Modelos registrados: {len(site._registry)}")

    # Verificar si Comanda está registrada
    from ventas.models import Comanda
    if Comanda in site._registry:
        print("✓ Comanda está registrada en admin")
    else:
        print("✗ Comanda NO está registrada en admin")

except Exception as e:
    print(f"✗ Error con admin site: {e}")

# 4. Verificar URLs
print("\n4. VERIFICANDO URLS")
print("-" * 40)

try:
    from django.urls import reverse
    admin_url = reverse('admin:index')
    print(f"✓ URL admin generada: {admin_url}")
except Exception as e:
    print(f"✗ Error generando URL admin: {e}")

# 5. Buscar el error específico
print("\n5. INTENTANDO CARGAR ADMIN MODULE")
print("-" * 40)

try:
    # Forzar recarga del módulo admin
    import importlib
    import ventas.admin
    importlib.reload(ventas.admin)
    print("✓ ventas.admin recargado exitosamente")
except Exception as e:
    print(f"✗ ERROR CRÍTICO al cargar ventas.admin:")
    print(f"  Tipo: {type(e).__name__}")
    print(f"  Mensaje: {str(e)}")
    print("\nTraceback completo:")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("RECOMENDACIONES:")
print("=" * 80)
print()
print("1. Si hay error en propiedades del modelo:")
print("   - Revisar las propiedades agregadas a Comanda")
print("   - Verificar que no haya errores de sintaxis")
print()
print("2. Si hay error en imports:")
print("   - Revisar circular imports")
print("   - Verificar que todos los modelos existan")
print()
print("3. SOLUCIÓN TEMPORAL:")
print("   - Comentar temporalmente el ComandaInline en VentaReservaAdmin")
print()
print("=" * 80)