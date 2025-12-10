#!/usr/bin/env python
"""
Script simplificado para migrar imágenes a Cloudinary.
Solo migra los servicios que tienen imágenes.
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
import requests

def setup_cloudinary():
    """Configura Cloudinary con las credenciales"""
    cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME')
    api_key = os.getenv('CLOUDINARY_API_KEY')
    api_secret = os.getenv('CLOUDINARY_API_SECRET')

    if not all([cloud_name, api_key, api_secret]):
        print("❌ Cloudinary no está configurado")
        return False

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret
    )

    print(f"✅ Cloudinary configurado: {cloud_name}")
    return True

def migrate_servicios():
    """Migra las imágenes de los servicios a Cloudinary"""
    from ventas.models import Servicio

    print("\n" + "="*60)
    print("MIGRACIÓN DE SERVICIOS A CLOUDINARY")
    print("="*60)

    # Obtener servicios con imágenes
    servicios = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
    total = servicios.count()

    print(f"\n📦 Servicios con imágenes: {total}")

    if total == 0:
        print("No hay servicios con imágenes para migrar")
        return

    migrated = 0
    failed = 0

    for i, servicio in enumerate(servicios, 1):
        try:
            print(f"\n[{i}/{total}] Procesando: {servicio.nombre}")

            if not servicio.imagen:
                print("   ⚠️ Sin imagen")
                continue

            # Obtener URL de la imagen
            image_url = None
            if hasattr(servicio.imagen, 'url'):
                image_url = servicio.imagen.url
                print(f"   URL actual: {image_url[:80]}...")

                # Verificar si ya está en Cloudinary
                if 'cloudinary.com' in image_url:
                    print("   ✓ Ya en Cloudinary")
                    continue

            # Intentar diferentes métodos para obtener la imagen
            image_content = None

            # Método 1: Descargar desde URL
            if image_url and image_url.startswith('http'):
                try:
                    print(f"   📥 Descargando desde URL...")
                    response = requests.get(image_url, timeout=30)
                    if response.status_code == 200:
                        image_content = response.content
                        print(f"   ✓ Descargado: {len(image_content)} bytes")
                except Exception as e:
                    print(f"   ⚠️ Error descargando: {e}")

            # Método 2: Leer archivo local
            if not image_content and hasattr(servicio.imagen, 'path'):
                try:
                    print(f"   📂 Leyendo archivo local...")
                    with open(servicio.imagen.path, 'rb') as f:
                        image_content = f.read()
                        print(f"   ✓ Leído: {len(image_content)} bytes")
                except Exception as e:
                    print(f"   ⚠️ Error leyendo archivo: {e}")

            # Método 3: Leer desde el storage
            if not image_content and hasattr(servicio.imagen, 'read'):
                try:
                    print(f"   📂 Leyendo desde storage...")
                    servicio.imagen.open('rb')
                    image_content = servicio.imagen.read()
                    servicio.imagen.close()
                    print(f"   ✓ Leído: {len(image_content)} bytes")
                except Exception as e:
                    print(f"   ⚠️ Error leyendo storage: {e}")

            if not image_content:
                print("   ❌ No se pudo obtener la imagen")
                failed += 1
                continue

            # Subir a Cloudinary
            try:
                print(f"   📤 Subiendo a Cloudinary...")
                result = cloudinary.uploader.upload(
                    image_content,
                    folder="aremko/servicios",
                    public_id=f"servicio_{servicio.id}_{servicio.nombre[:20].replace(' ', '_')}",
                    overwrite=True,
                    resource_type="image",
                    tags=["servicio", "migrado"],
                    eager=[
                        {"width": 200, "height": 200, "crop": "thumb"},
                        {"width": 500, "crop": "scale", "quality": "auto"},
                        {"width": 800, "height": 600, "crop": "fit"}
                    ]
                )

                print(f"   ✅ Subido exitosamente")
                print(f"   📎 URL: {result['secure_url'][:80]}...")
                print(f"   📎 Public ID: {result['public_id']}")

                # Actualizar la URL en el modelo
                # Nota: En producción, Django-cloudinary-storage manejará esto automáticamente
                # Por ahora solo registramos el éxito

                migrated += 1

            except Exception as e:
                print(f"   ❌ Error subiendo a Cloudinary: {e}")
                failed += 1

        except Exception as e:
            print(f"   ❌ Error procesando servicio: {e}")
            failed += 1

    # Resumen
    print("\n" + "="*60)
    print("RESUMEN DE LA MIGRACIÓN")
    print("="*60)
    print(f"✅ Migradas exitosamente: {migrated}")
    print(f"❌ Fallidas: {failed}")
    print(f"📊 Total procesadas: {migrated + failed}")

    if migrated > 0:
        print("\n✨ Migración completada!")
        print("\n📌 Verifica las imágenes en:")
        print("   https://console.cloudinary.com/console/media_library")

def main():
    """Función principal"""

    if not setup_cloudinary():
        print("❌ No se puede continuar sin Cloudinary configurado")
        return

    # Preguntar confirmación
    print("\n⚠️ Este script migrará las imágenes de servicios a Cloudinary")
    response = input("\n¿Deseas continuar? (s/n): ")

    if response.lower() != 's':
        print("Migración cancelada")
        return

    migrate_servicios()

if __name__ == "__main__":
    main()