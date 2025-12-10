#!/usr/bin/env python
"""
Script para diagnosticar qué pasa cuando se sube una nueva imagen.
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

from ventas.models import Servicio
from django.conf import settings
import requests

print("=" * 60)
print("DIAGNÓSTICO: IMÁGENES SUBIDAS RECIENTEMENTE")
print("=" * 60)

# Verificar configuración de Cloudinary
print("\n🔧 CONFIGURACIÓN ACTUAL:")
print("-" * 40)
print(f"DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")

if hasattr(settings, 'CLOUDINARY_STORAGE'):
    cloud_config = settings.CLOUDINARY_STORAGE
    print(f"CLOUDINARY_CLOUD_NAME: {cloud_config.get('CLOUD_NAME')}")
    print(f"SECURE: {cloud_config.get('SECURE')}")

# Buscar la Tina Llaima que acabas de actualizar
print("\n🔍 BUSCANDO TINA LLAIMA:")
print("-" * 40)

tina_llaima = Servicio.objects.filter(nombre__icontains='llaima').first()

if tina_llaima:
    print(f"\n✓ Servicio encontrado: {tina_llaima.nombre} (ID: {tina_llaima.id})")

    if tina_llaima.imagen:
        print(f"\n📦 CAMPO IMAGEN:")
        print(f"  imagen (objeto): {tina_llaima.imagen}")
        print(f"  imagen.name: '{tina_llaima.imagen.name}'")
        print(f"  imagen.path (si existe): ", end="")
        try:
            print(tina_llaima.imagen.path)
        except:
            print("N/A (Cloudinary no tiene path local)")

        print(f"\n🌐 URL GENERADA:")
        try:
            url = tina_llaima.imagen.url
            print(f"  imagen.url: {url}")

            # Analizar la URL
            print(f"\n🔬 ANÁLISIS DE LA URL:")
            if url.count('http') > 1:
                print(f"  ❌ URL contiene 'http' múltiples veces")
            if url.count('//') > 2:
                print(f"  ❌ URL contiene '//' múltiples veces")
            if 'cloudinary.com' in url:
                print(f"  ✓ Es una URL de Cloudinary")

            # Intentar acceder
            print(f"\n🌍 VERIFICACIÓN DE ACCESIBILIDAD:")
            try:
                response = requests.head(url, timeout=10)
                print(f"  HTTP Status: {response.status_code}")

                if response.status_code == 200:
                    print(f"  ✅ Imagen ACCESIBLE")
                    print(f"  Content-Type: {response.headers.get('Content-Type', 'N/A')}")
                elif response.status_code == 404:
                    print(f"  ❌ Imagen NO ENCONTRADA (404)")
                else:
                    print(f"  ⚠️ Respuesta inesperada")

            except Exception as e:
                print(f"  ❌ Error al verificar: {e}")

        except Exception as e:
            print(f"  ❌ Error generando URL: {e}")
    else:
        print(f"  ❌ El servicio NO tiene imagen asignada")
else:
    print("❌ No se encontró el servicio Tina Llaima")

# Mostrar los últimos 5 servicios con imagen
print("\n📋 ÚLTIMOS 5 SERVICIOS CON IMAGEN:")
print("-" * 40)

servicios_recientes = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True).order_by('-id')[:5]

for s in servicios_recientes:
    print(f"\n• {s.nombre} (ID: {s.id})")
    print(f"  imagen.name: {s.imagen.name}")
    try:
        url = s.imagen.url
        print(f"  URL: {url[:80]}...")

        # Quick check
        if url.startswith('https://res.cloudinary.com/'):
            parts = url.replace('https://res.cloudinary.com/', '').split('/')
            if len(parts) >= 2:
                print(f"  Cloud: {parts[0]}, Path: {'/'.join(parts[1:])}")
    except Exception as e:
        print(f"  ❌ Error: {e}")

print("\n" + "=" * 60)
print("RECOMENDACIONES")
print("=" * 60)

print("""
Si la imagen que acabas de subir:

1. ❌ Tiene imagen.name con URL completa (empieza con 'http'):
   → El problema está en cómo Django guarda la imagen
   → Necesitamos revisar la configuración de CLOUDINARY_STORAGE

2. ❌ Tiene URL correcta pero devuelve 404:
   → La imagen no se subió realmente a Cloudinary
   → Verificar credenciales de API

3. ❌ Tiene imagen.name correcto pero URL duplicada:
   → Hay un problema en cómo CloudinaryStorage genera las URLs
   → Necesitamos revisar MEDIA_URL

Por favor ejecuta este script y comparte el resultado completo.
""")
