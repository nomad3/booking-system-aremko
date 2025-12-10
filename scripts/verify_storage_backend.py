#!/usr/bin/env python
"""
Script para verificar qué backend de storage se está usando.
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
from ventas.models import Servicio

print("=" * 60)
print("VERIFICACIÓN: BACKEND DE STORAGE")
print("=" * 60)

print("\n🔧 VARIABLES DE ENTORNO:")
print("-" * 40)
print(f"CLOUDINARY_CLOUD_NAME: {'✓ Configurado' if os.getenv('CLOUDINARY_CLOUD_NAME') else '✗ NO configurado'}")
print(f"CLOUDINARY_API_KEY: {'✓ Configurado' if os.getenv('CLOUDINARY_API_KEY') else '✗ NO configurado'}")
print(f"CLOUDINARY_API_SECRET: {'✓ Configurado' if os.getenv('CLOUDINARY_API_SECRET') else '✗ NO configurado'}")
print(f"GCS_CREDENTIALS_JSON: {'✓ Configurado' if os.getenv('GCS_CREDENTIALS_JSON') else '✗ NO configurado'}")

print("\n📦 CONFIGURACIÓN DE DJANGO:")
print("-" * 40)
print(f"DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")

if hasattr(settings, 'CLOUDINARY_STORAGE'):
    print("\n☁️ CLOUDINARY_STORAGE está configurado:")
    for key, value in settings.CLOUDINARY_STORAGE.items():
        if key != 'API_SECRET':  # No mostrar el secreto
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: ***")

if hasattr(settings, 'GS_BUCKET_NAME'):
    print(f"\n☁️ GCS está configurado:")
    print(f"  GS_BUCKET_NAME: {settings.GS_BUCKET_NAME}")

print("\n" + "=" * 60)
print("DIAGNÓSTICO")
print("=" * 60)

if 'cloudinary' in settings.DEFAULT_FILE_STORAGE.lower():
    print("✅ USANDO CLOUDINARY")
    print("\nLas nuevas imágenes que subas se guardarán en Cloudinary.")
elif 'gcloud' in settings.DEFAULT_FILE_STORAGE.lower() or 'google' in settings.DEFAULT_FILE_STORAGE.lower():
    print("⚠️ USANDO GOOGLE CLOUD STORAGE")
    print("\n❌ PROBLEMA DETECTADO:")
    print("Las imágenes se están subiendo a GCS, no a Cloudinary.")
    print("\n🔧 SOLUCIÓN:")
    print("1. Ve a Render Dashboard > tu servicio > Environment")
    print("2. ELIMINA la variable GCS_CREDENTIALS_JSON")
    print("3. Verifica que estas variables estén configuradas:")
    print("   - CLOUDINARY_CLOUD_NAME")
    print("   - CLOUDINARY_API_KEY")
    print("   - CLOUDINARY_API_SECRET")
    print("4. Reinicia el servicio")
else:
    print("⚠️ USANDO ALMACENAMIENTO LOCAL")
    print("\n❌ PROBLEMA DETECTADO:")
    print("Ni Cloudinary ni GCS están configurados correctamente.")

# Verificar una imagen existente
print("\n📸 VERIFICANDO IMAGEN DE PRUEBA:")
print("-" * 40)

servicio = Servicio.objects.filter(imagen__isnull=False).exclude(imagen='').first()
if servicio:
    print(f"\nServicio: {servicio.nombre}")
    print(f"imagen.name: {servicio.imagen.name}")
    print(f"imagen.url: {servicio.imagen.url}")

    # Detectar de dónde viene
    if 'cloudinary.com' in servicio.imagen.url:
        print("✓ Esta imagen está en Cloudinary")
    elif 'googleapis.com' in servicio.imagen.url or 'storage.cloud.google.com' in servicio.imagen.url:
        print("✓ Esta imagen está en Google Cloud Storage")
    else:
        print("? Origen desconocido")
else:
    print("No se encontraron servicios con imágenes")

print("\n" + "=" * 60)
