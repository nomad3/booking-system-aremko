#!/usr/bin/env python
"""
Script para verificar y actualizar la descripción de experiencias de GiftCard
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import GiftCardExperiencia

print("=" * 80)
print("VERIFICACIÓN DE DESCRIPCIONES DE EXPERIENCIAS")
print("=" * 80)

# Buscar experiencias sin descripción
print("\n🔍 Buscando experiencias...")

experiencias = GiftCardExperiencia.objects.all().order_by('categoria', 'nombre')

print(f"Total de experiencias: {experiencias.count()}\n")

sin_descripcion = []
con_descripcion = []

for exp in experiencias:
    print(f"ID: {exp.id_experiencia}")
    print(f"   Nombre: {exp.nombre}")
    print(f"   Categoría: {exp.categoria}")
    print(f"   Descripción: {exp.descripcion if exp.descripcion else '❌ VACÍO'}")
    print()

    if not exp.descripcion or exp.descripcion.strip() == '':
        sin_descripcion.append(exp)
    else:
        con_descripcion.append(exp)

print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)
print(f"✅ Con descripción: {len(con_descripcion)}")
print(f"❌ Sin descripción: {len(sin_descripcion)}")

if sin_descripcion:
    print("\n⚠️ Experiencias SIN descripción:")
    for exp in sin_descripcion:
        print(f"   - {exp.nombre} (ID: {exp.id_experiencia})")

print("\n" + "=" * 80)
