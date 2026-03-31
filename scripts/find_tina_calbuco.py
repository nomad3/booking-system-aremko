#!/usr/bin/env python
"""
Script para encontrar el ID correcto de Tina Calbuco
Ejecutar: python scripts/find_tina_calbuco.py
"""

import os
import sys
import django

# Add the project root to the path
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    django.setup()
except Exception:
    # Try alternative settings module names
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    try:
        django.setup()
    except Exception:
        # Try to find settings module
        import importlib.util
        for possible_name in ['aremko_project.settings', 'config.settings', 'mysite.settings']:
            try:
                os.environ['DJANGO_SETTINGS_MODULE'] = possible_name
                django.setup()
                break
            except:
                continue

from ventas.models import Servicio, CategoriaServicio
from django.db.models import Q

print("\n" + "="*60)
print("BUSCANDO TINA CALBUCO")
print("="*60)

# Buscar todas las tinajas
print("\n1. SERVICIOS QUE CONTIENEN 'TINA' O 'CALBUCO':")
print("-" * 40)
tinajas = Servicio.objects.filter(
    Q(nombre__icontains='tina') |
    Q(nombre__icontains='tinaja') |
    Q(nombre__icontains='calbuco')
).order_by('id')

calbuco_id = None
for tina in tinajas:
    is_active = "✅" if tina.activo else "❌"
    is_web = "✅" if tina.publicado_web else "❌"
    print(f"ID {tina.id:3d}: {tina.nombre:30s} Activo:{is_active} Web:{is_web}")
    if 'calbuco' in tina.nombre.lower():
        calbuco_id = tina.id
        print(f"         ⭐ POSIBLE TINA CALBUCO ENCONTRADA!")

# Buscar por categoría
print("\n2. SERVICIOS POR CATEGORÍA 'TINAJAS':")
print("-" * 40)
cat_tinajas = CategoriaServicio.objects.filter(
    Q(nombre__icontains='tina') |
    Q(nombre__icontains='tinaja')
).first()

if cat_tinajas:
    print(f"Categoría encontrada: {cat_tinajas.nombre} (ID: {cat_tinajas.id})")
    servicios = Servicio.objects.filter(categoria=cat_tinajas).order_by('id')
    print(f"Servicios en esta categoría:")
    for s in servicios:
        is_active = "✅" if s.activo else "❌"
        is_web = "✅" if s.publicado_web else "❌"
        print(f"  ID {s.id:3d}: {s.nombre:30s} Activo:{is_active} Web:{is_web}")
        if 'calbuco' in s.nombre.lower():
            calbuco_id = s.id
            print(f"           ⭐ TINA CALBUCO ENCONTRADA EN CATEGORÍA!")
else:
    print("No se encontró categoría de Tinajas")

# Resumen
print("\n" + "="*60)
print("RESUMEN")
print("="*60)

if calbuco_id:
    calbuco = Servicio.objects.get(id=calbuco_id)
    print(f"\n✅ TINA CALBUCO ENCONTRADA:")
    print(f"   ID: {calbuco.id}")
    print(f"   Nombre: {calbuco.nombre}")
    print(f"   Activo: {calbuco.activo}")
    print(f"   Publicado web: {calbuco.publicado_web}")
    print(f"   Precio: ${calbuco.precio_base:,.0f}")

    # Verificar slots
    if hasattr(calbuco, 'slots_disponibles') and calbuco.slots_disponibles:
        if isinstance(calbuco.slots_disponibles, dict):
            print(f"\n   Días configurados en slots_disponibles:")
            for dia in calbuco.slots_disponibles.keys():
                slots = calbuco.slots_disponibles[dia]
                print(f"      {dia}: {len(slots) if slots else 0} slots")
        else:
            print(f"   Slots configurados (tipo: {type(calbuco.slots_disponibles)})")
    else:
        print("   ⚠️  No tiene slots configurados")

    print(f"\n   URL de prueba para mañana:")
    from datetime import datetime, timedelta
    tomorrow = datetime.now().date() + timedelta(days=1)
    print(f"   https://aremko.cl/ventas/get-available-hours/?servicio_id={calbuco.id}&fecha={tomorrow}")
else:
    print("\n❌ NO SE ENCONTRÓ TINA CALBUCO")
    print("   Verifica que el servicio exista en la base de datos")

print("\n" + "="*60)