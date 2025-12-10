#!/usr/bin/env python
"""
Script para verificar las URLs de las imágenes después de subir.
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

print("=" * 60)
print("VERIFICACIÓN DE URLs DE IMÁGENES")
print("=" * 60)

# Buscar el servicio 14 que fue editado
try:
    servicio = Servicio.objects.get(pk=14)
    print(f"\n📦 Servicio: {servicio.nombre}")
    print("-" * 40)

    if servicio.imagen:
        print(f"✓ Campo imagen tiene valor")
        print(f"  Nombre archivo: {servicio.imagen.name}")
        print(f"  Tamaño: {servicio.imagen.size if hasattr(servicio.imagen, 'size') else 'N/A'} bytes")

        # Intentar obtener la URL
        try:
            url = servicio.imagen.url
            print(f"  URL generada: {url}")

            # Verificar el formato de la URL
            if 'cloudinary.com' in url:
                print("  ✅ URL de Cloudinary detectada")

                # Verificar si la URL tiene el formato correcto
                if 'res.cloudinary.com' in url:
                    print("  ✅ Formato de URL correcto")
                else:
                    print("  ⚠️ URL de Cloudinary pero formato extraño")

                # Extraer información de la URL
                if '/upload/' in url:
                    parts = url.split('/upload/')
                    if len(parts) > 1:
                        print(f"  Transformaciones: {parts[1].split('/')[0] if '/' in parts[1] else 'ninguna'}")

            else:
                print("  ⚠️ URL no es de Cloudinary")

        except Exception as e:
            print(f"  ❌ Error obteniendo URL: {e}")

    else:
        print("❌ El servicio no tiene imagen asignada")

except Servicio.DoesNotExist:
    print("❌ Servicio 14 no encontrado")

# Verificar otros servicios con imágenes recientes
print("\n📋 ÚLTIMOS 5 SERVICIOS CON IMÁGENES:")
print("-" * 40)

servicios = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True).order_by('-actualizado')[:5]

for s in servicios:
    try:
        print(f"\n• {s.nombre}")
        print(f"  Archivo: {s.imagen.name}")
        print(f"  URL: {s.imagen.url[:100]}...")

        # Verificar si la URL es accesible
        if s.imagen.url.startswith('http'):
            import requests
            try:
                response = requests.head(s.imagen.url, timeout=5)
                if response.status_code == 200:
                    print(f"  ✅ Imagen accesible (HTTP {response.status_code})")
                else:
                    print(f"  ⚠️ HTTP {response.status_code}")
            except:
                print(f"  ⚠️ No se pudo verificar accesibilidad")

    except Exception as e:
        print(f"  ❌ Error: {e}")

# Verificar la configuración del storage
print("\n🔧 CONFIGURACIÓN DEL STORAGE:")
print("-" * 40)

from django.core.files.storage import default_storage
from django.conf import settings

print(f"Storage backend: {settings.DEFAULT_FILE_STORAGE}")

# Probar crear una URL directamente
test_path = "servicios/test_image.jpg"
try:
    test_url = default_storage.url(test_path)
    print(f"URL de prueba generada: {test_url}")

    if 'https://res.cloudinary.com' in test_url:
        print("✅ URLs se generan correctamente con Cloudinary")
    else:
        print("⚠️ URLs no tienen el formato esperado de Cloudinary")

except Exception as e:
    print(f"❌ Error generando URL de prueba: {e}")

print("\n" + "=" * 60)
print("DIAGNÓSTICO:")
print("=" * 60)

print("\nSi las imágenes no se ven, verifica:")
print("1. Que la URL generada sea válida y accesible")
print("2. Que el template use {{ servicio.imagen.url }} correctamente")
print("3. Que no haya problemas de CORS o permisos en Cloudinary")
print("4. Revisar la consola del navegador para errores 404 o 403")

print("\n" + "=" * 60)