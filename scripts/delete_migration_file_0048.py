#!/usr/bin/env python3
"""
Script para eliminar físicamente el archivo de migración problemático
0048_update_category_hero_images.py del sistema de archivos.

Ejecutar desde Render: python scripts/delete_migration_file_0048.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

print("\n" + "=" * 80)
print("ELIMINAR ARCHIVO DE MIGRACIÓN PROBLEMÁTICO")
print("=" * 80)

# Ruta al archivo problemático
migration_file = BASE_DIR / "ventas" / "migrations" / "0048_update_category_hero_images.py"

print(f"\n🔍 Buscando archivo: {migration_file}")
print("-" * 80)

if migration_file.exists():
    print("⚠️  Archivo encontrado - procediendo a eliminarlo...")
    try:
        migration_file.unlink()
        print("✅ Archivo eliminado exitosamente!")
    except Exception as e:
        print(f"❌ Error al eliminar: {e}")
        sys.exit(1)
else:
    print("✅ El archivo NO existe (ya fue eliminado o renombrado)")

# Verificar que el archivo 0067 existe
migration_file_067 = BASE_DIR / "ventas" / "migrations" / "0067_update_category_hero_images.py"

print(f"\n🔍 Verificando que existe 0067: {migration_file_067}")
print("-" * 80)

if migration_file_067.exists():
    print("✅ El archivo 0067_update_category_hero_images.py existe correctamente")
else:
    print("⚠️  ADVERTENCIA: El archivo 0067_update_category_hero_images.py NO existe")

# Verificar archivo 0066
migration_file_066 = BASE_DIR / "ventas" / "migrations" / "0066_add_web_fields_to_producto.py"

print(f"\n🔍 Verificando que existe 0066: {migration_file_066}")
print("-" * 80)

if migration_file_066.exists():
    print("✅ El archivo 0066_add_web_fields_to_producto.py existe correctamente")
else:
    print("⚠️  ADVERTENCIA: El archivo 0066_add_web_fields_to_producto.py NO existe")

# Listar todos los archivos 0048 en migrations
migrations_dir = BASE_DIR / "ventas" / "migrations"
print(f"\n📋 Archivos 0048* en {migrations_dir}:")
print("-" * 80)

files_0048 = list(migrations_dir.glob("0048*.py"))
if files_0048:
    for f in files_0048:
        print(f"   - {f.name}")
else:
    print("   (ninguno)")

print("\n" + "=" * 80)
print("SIGUIENTE PASO")
print("=" * 80)
print("\n🚀 Ahora ejecuta:")
print("   python manage.py migrate ventas")
print("\n" + "=" * 80)
print("FIN DEL SCRIPT")
print("=" * 80 + "\n")
