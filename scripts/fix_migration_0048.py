#!/usr/bin/env python3
"""
Script para eliminar la migración problemática 0048_update_category_hero_images
de la base de datos y permitir que las migraciones 0066 y 0067 se ejecuten.

Ejecutar desde Render: python scripts/fix_migration_0048.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from django.db.migrations.recorder import MigrationRecorder

print("\n" + "=" * 80)
print("LIMPIEZA DE MIGRACIÓN PROBLEMÁTICA 0048")
print("=" * 80)

# Paso 1: Ver qué migraciones 0048 están registradas
print("\n🔍 Buscando migraciones 0048 en la base de datos...")
print("-" * 80)

migrations_0048 = MigrationRecorder.Migration.objects.filter(
    app='ventas',
    name__startswith='0048'
)

if migrations_0048.exists():
    print(f"📋 Encontradas {migrations_0048.count()} migración(es) 0048:")
    for m in migrations_0048:
        print(f"   - {m.name}")
else:
    print("✅ No se encontraron migraciones 0048 registradas")

# Paso 2: Buscar específicamente la problemática
print("\n🎯 Buscando la migración problemática específica...")
print("-" * 80)

problematic = MigrationRecorder.Migration.objects.filter(
    app='ventas',
    name='0048_update_category_hero_images'
)

if problematic.exists():
    print("⚠️  Encontrada migración problemática: 0048_update_category_hero_images")
    print("   Esta migración tiene una dependencia incorrecta y debe ser eliminada")

    # Eliminar
    print("\n🗑️  Eliminando migración problemática de la base de datos...")
    count = problematic.delete()[0]
    print(f"✅ Eliminadas {count} entrada(s) de django_migrations")

else:
    print("✅ La migración problemática NO está en la base de datos")
    print("   (Ya fue eliminada o nunca se aplicó)")

# Paso 3: Verificar estado final
print("\n📊 Estado final de migraciones 0048...")
print("-" * 80)

migrations_0048_after = MigrationRecorder.Migration.objects.filter(
    app='ventas',
    name__startswith='0048'
)

if migrations_0048_after.exists():
    print("📋 Migraciones 0048 restantes:")
    for m in migrations_0048_after:
        print(f"   - {m.name}")
else:
    print("✅ No quedan migraciones 0048_update_category_hero_images")

# Paso 4: Verificar migraciones 0066 y 0067
print("\n📊 Verificando migraciones 0066 y 0067...")
print("-" * 80)

mig_0066 = MigrationRecorder.Migration.objects.filter(
    app='ventas',
    name='0066_add_web_fields_to_producto'
).exists()

mig_0067 = MigrationRecorder.Migration.objects.filter(
    app='ventas',
    name='0067_update_category_hero_images'
).exists()

print(f"0066_add_web_fields_to_producto: {'✅ Aplicada' if mig_0066 else '⏳ Pendiente'}")
print(f"0067_update_category_hero_images: {'✅ Aplicada' if mig_0067 else '⏳ Pendiente'}")

# Paso 5: Instrucciones finales
print("\n" + "=" * 80)
print("SIGUIENTE PASO")
print("=" * 80)

if not mig_0066 or not mig_0067:
    print("\n✅ La limpieza fue exitosa!")
    print("\n🚀 Ahora ejecuta:")
    print("   python manage.py migrate ventas")
    print("\nEsto aplicará las migraciones 0066 y 0067 correctamente.")
else:
    print("\n✅ Las migraciones ya están aplicadas!")
    print("   No es necesario ejecutar migrate nuevamente.")

print("\n" + "=" * 80)
print("FIN DEL SCRIPT")
print("=" * 80 + "\n")
