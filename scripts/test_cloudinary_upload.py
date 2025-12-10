#!/usr/bin/env python
"""
Script para probar si podemos subir imágenes a Cloudinary.
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

from django.conf import settings
import cloudinary
import cloudinary.uploader
from PIL import Image
import io

print("=" * 60)
print("TEST: SUBIDA DIRECTA A CLOUDINARY")
print("=" * 60)

# Configurar Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_STORAGE['CLOUD_NAME'],
    api_key=settings.CLOUDINARY_STORAGE['API_KEY'],
    api_secret=settings.CLOUDINARY_STORAGE['API_SECRET'],
    secure=True
)

print("\n📋 CONFIGURACIÓN:")
print("-" * 40)
print(f"Cloud Name: {settings.CLOUDINARY_STORAGE['CLOUD_NAME']}")
print(f"API Key: {settings.CLOUDINARY_STORAGE['API_KEY']}")
print(f"Secure: {settings.CLOUDINARY_STORAGE['SECURE']}")

# Crear una imagen de prueba simple
print("\n🎨 CREANDO IMAGEN DE PRUEBA...")
print("-" * 40)

# Crear una imagen roja simple de 100x100
img = Image.new('RGB', (100, 100), color=(255, 0, 0))
img_buffer = io.BytesIO()
img.save(img_buffer, format='PNG')
img_buffer.seek(0)

print("✓ Imagen de prueba creada (100x100, roja)")

# Intentar subir
print("\n☁️ INTENTANDO SUBIR A CLOUDINARY...")
print("-" * 40)

try:
    result = cloudinary.uploader.upload(
        img_buffer,
        public_id='test_upload_from_script',
        folder='servicios',
        overwrite=True,
        resource_type='image'
    )

    print("✅ ¡SUBIDA EXITOSA!")
    print(f"\nDetalles:")
    print(f"  Public ID: {result.get('public_id')}")
    print(f"  URL: {result.get('secure_url')}")
    print(f"  Format: {result.get('format')}")
    print(f"  Width: {result.get('width')}")
    print(f"  Height: {result.get('height')}")
    print(f"  Bytes: {result.get('bytes')}")

    # Verificar que sea accesible
    print("\n🌍 VERIFICANDO ACCESIBILIDAD...")
    print("-" * 40)

    import requests
    response = requests.head(result.get('secure_url'), timeout=10)

    if response.status_code == 200:
        print("✅ Imagen accesible en la URL")
    else:
        print(f"⚠️ HTTP {response.status_code}")

    print("\n" + "=" * 60)
    print("✅ CLOUDINARY FUNCIONA CORRECTAMENTE")
    print("=" * 60)
    print("\nEl problema NO es con las credenciales de Cloudinary.")
    print("El problema debe estar en cómo django-cloudinary-storage")
    print("maneja la subida desde Django Admin.")

except cloudinary.exceptions.Error as e:
    print(f"❌ ERROR DE CLOUDINARY: {e}")
    print("\n🔧 POSIBLES CAUSAS:")
    print("1. Credenciales incorrectas")
    print("2. Permisos insuficientes en la cuenta de Cloudinary")
    print("3. Límites de cuota excedidos")

except Exception as e:
    print(f"❌ ERROR GENERAL: {e}")
    print(f"Tipo: {type(e).__name__}")

print("\n" + "=" * 60)
