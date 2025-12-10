#!/usr/bin/env python
"""
Script para verificar las variables de entorno de Cloudinary.
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

print("=" * 60)
print("VERIFICACIÓN DE VARIABLES DE ENTORNO")
print("=" * 60)

# Variables de Cloudinary
cloudinary_vars = {
    'CLOUDINARY_CLOUD_NAME': os.getenv('CLOUDINARY_CLOUD_NAME'),
    'CLOUDINARY_API_KEY': os.getenv('CLOUDINARY_API_KEY'),
    'CLOUDINARY_API_SECRET': os.getenv('CLOUDINARY_API_SECRET'),
}

print("\n📋 Variables de Cloudinary:")
print("-" * 40)

all_configured = True
for var_name, var_value in cloudinary_vars.items():
    if var_value:
        if 'SECRET' in var_name:
            # Ocultar parcialmente el secret
            display_value = var_value[:5] + '...' + var_value[-5:] if len(var_value) > 10 else '***'
            print(f"✅ {var_name}: {display_value}")
        else:
            print(f"✅ {var_name}: {var_value}")
    else:
        print(f"❌ {var_name}: NO CONFIGURADA")
        all_configured = False

# Verificar configuración de Django
print("\n📋 Configuración de Django:")
print("-" * 40)

try:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
    import django
    django.setup()

    from django.conf import settings

    print(f"DEFAULT_FILE_STORAGE: {getattr(settings, 'DEFAULT_FILE_STORAGE', 'No configurado')}")
    print(f"MEDIA_URL: {getattr(settings, 'MEDIA_URL', 'No configurado')}")

    # Verificar si Cloudinary está configurado en Django
    if 'cloudinary' in getattr(settings, 'DEFAULT_FILE_STORAGE', '').lower():
        print("✅ Cloudinary está configurado como storage en Django")
    else:
        print("⚠️  Cloudinary NO está configurado como storage en Django")

except Exception as e:
    print(f"❌ Error al cargar configuración de Django: {e}")

print("\n" + "=" * 60)

if all_configured:
    print("✅ TODAS LAS VARIABLES ESTÁN CONFIGURADAS")
    print("\nPuedes proceder con la migración:")
    print("  python scripts/migrate_to_cloudinary.py")
else:
    print("❌ FALTAN VARIABLES POR CONFIGURAR")
    print("\nAsegúrate de configurar en Render:")
    print("  - CLOUDINARY_CLOUD_NAME")
    print("  - CLOUDINARY_API_KEY")
    print("  - CLOUDINARY_API_SECRET")

print("=" * 60)