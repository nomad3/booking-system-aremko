#!/usr/bin/env python
"""
Script para probar subida directa a Cloudinary sin Django.
"""

import os
import cloudinary
import cloudinary.uploader
from PIL import Image
import io
import requests

print("=" * 60)
print("TEST: SUBIDA DIRECTA A CLOUDINARY")
print("=" * 60)

# Configurar Cloudinary desde variables de entorno
cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
api_key = os.getenv('CLOUDINARY_API_KEY')
api_secret = os.getenv('CLOUDINARY_API_SECRET')

print("\n📋 CONFIGURACIÓN:")
print("-" * 40)
print(f"Cloud Name: {cloud_name}")
print(f"API Key: {api_key}")
print(f"API Secret: {'***' if api_secret else 'NO CONFIGURADO'}")

if not cloud_name or not api_key or not api_secret:
    print("\n❌ ERROR: Faltan credenciales de Cloudinary")
    print("Verifica que las variables de entorno estén configuradas.")
    exit(1)

cloudinary.config(
    cloud_name=cloud_name,
    api_key=api_key,
    api_secret=api_secret,
    secure=True
)

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
        public_id='test_upload_direct',
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

    url = result.get('secure_url')
    response = requests.head(url, timeout=10)

    if response.status_code == 200:
        print(f"✅ Imagen accesible en: {url}")
        print(f"   Content-Type: {response.headers.get('Content-Type')}")
    else:
        print(f"⚠️ HTTP {response.status_code}")

    print("\n" + "=" * 60)
    print("✅ CLOUDINARY FUNCIONA CORRECTAMENTE")
    print("=" * 60)
    print("\nCONCLUSIÓN:")
    print("Las credenciales de Cloudinary están bien.")
    print("El problema está en la integración con django-cloudinary-storage.")
    print("\n💡 POSIBLES CAUSAS:")
    print("1. Configuración incorrecta de CLOUDINARY_STORAGE en settings.py")
    print("2. Problema con el campo ImageField en el modelo")
    print("3. Error en el proceso de upload del admin de Django")

except cloudinary.exceptions.Error as e:
    print(f"\n❌ ERROR DE CLOUDINARY: {e}")
    print("\n🔧 POSIBLES CAUSAS:")
    print("1. Credenciales incorrectas")
    print("2. Permisos insuficientes en la cuenta de Cloudinary")
    print("3. Límites de cuota excedidos")
    print("\n💡 VERIFICA EN:")
    print("   https://console.cloudinary.com")

except Exception as e:
    print(f"\n❌ ERROR GENERAL: {e}")
    print(f"   Tipo: {type(e).__name__}")

print("\n" + "=" * 60)
