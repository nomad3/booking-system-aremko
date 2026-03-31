#!/usr/bin/env python
"""
Script para listar regiones y comunas
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Region, Comuna

print("\n" + "="*80)
print("REGIONES Y COMUNAS")
print("="*80)

regiones = Region.objects.all().order_by('id')

for region in regiones:
    print(f"\nRegión ID: {region.id} | {region.nombre}")
    comunas = region.comunas.all().order_by('nombre')[:5]  # Mostrar solo primeras 5
    for comuna in comunas:
        print(f"  - Comuna ID: {comuna.id:3d} | {comuna.nombre}")
    if region.comunas.count() > 5:
        print(f"  ... ({region.comunas.count() - 5} comunas más)")

print("\n" + "="*80)
