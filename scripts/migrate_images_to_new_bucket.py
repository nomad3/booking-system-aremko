#!/usr/bin/env python
"""
Script para migrar imágenes desde el bucket antiguo de GCS al nuevo bucket.
Útil cuando se cambia de cuenta o se reconfigura Google Cloud Storage.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio, Cabaña, Tina, Masaje, TipoCabaña
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import requests
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_image(url):
    """Descarga una imagen desde una URL"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content
        else:
            logger.error(f"Error {response.status_code} descargando: {url}")
            return None
    except Exception as e:
        logger.error(f"Error descargando {url}: {e}")
        return None

def migrate_model_images(model_class, image_field='imagen'):
    """Migra imágenes de un modelo al nuevo bucket"""

    model_name = model_class.__name__
    print(f"\n{'='*50}")
    print(f"📦 Migrando imágenes de: {model_name}")
    print(f"{'='*50}")

    # Obtener configuración actual
    bucket_name = getattr(settings, 'GS_BUCKET_NAME', '')
    old_buckets = ['aremkoweb', 'aremko-e51ae']  # Buckets antiguos conocidos

    migrated = 0
    failed = 0
    skipped = 0
    no_image = 0

    # Procesar todos los objetos del modelo
    objects = model_class.objects.all()
    total = objects.count()

    print(f"Total de registros: {total}")

    for i, obj in enumerate(objects, 1):
        # Obtener el campo de imagen
        image = getattr(obj, image_field, None)

        # Si no tiene imagen, skip
        if not image or not image.name:
            no_image += 1
            continue

        try:
            # Obtener URL actual de la imagen
            current_url = image.url if hasattr(image, 'url') else str(image)

            # Verificar si ya está en el nuevo bucket
            if bucket_name and bucket_name in current_url:
                print(f"  [{i}/{total}] ✓ {obj}: Ya en el bucket correcto")
                skipped += 1
                continue

            # Verificar si es una URL de GCS antigua
            is_old_gcs = any(bucket in current_url for bucket in old_buckets)

            if is_old_gcs or current_url.startswith('http'):
                print(f"  [{i}/{total}] 🔄 {obj}: Migrando desde {current_url[:60]}...")

                # Descargar la imagen
                image_content = download_image(current_url)

                if image_content:
                    # Obtener el nombre del archivo
                    filename = os.path.basename(urlparse(current_url).path)
                    if not filename:
                        filename = f"{model_name.lower()}_{obj.pk}.jpg"

                    # Crear nuevo archivo
                    new_file = ContentFile(image_content, name=filename)

                    # Guardar en el campo de imagen
                    image.save(filename, new_file, save=True)

                    # Obtener nueva URL
                    new_url = image.url if hasattr(image, 'url') else 'Guardado localmente'

                    print(f"      ✅ Migrado exitosamente")
                    print(f"      Nueva URL: {new_url[:60]}...")
                    migrated += 1
                else:
                    print(f"      ❌ No se pudo descargar la imagen")
                    failed += 1
            else:
                # Imagen local o ya migrada
                print(f"  [{i}/{total}] ✓ {obj}: Imagen local o ya migrada")
                skipped += 1

        except Exception as e:
            print(f"  [{i}/{total}] ❌ {obj}: Error - {e}")
            failed += 1

    # Resumen del modelo
    print(f"\n📊 Resumen {model_name}:")
    print(f"  • Total procesados: {total}")
    print(f"  • Sin imagen: {no_image}")
    print(f"  • Migradas: {migrated}")
    print(f"  • Ya correctas: {skipped}")
    print(f"  • Fallidas: {failed}")

    return migrated, failed, skipped, no_image

def verify_current_configuration():
    """Verifica la configuración actual de almacenamiento"""
    print("\n" + "="*60)
    print("🔍 CONFIGURACIÓN ACTUAL DE ALMACENAMIENTO")
    print("="*60)

    storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', 'No configurado')
    is_gcs = 'gcloud' in storage_backend.lower()

    print(f"Backend: {storage_backend}")

    if is_gcs:
        bucket_name = getattr(settings, 'GS_BUCKET_NAME', 'No configurado')
        project_id = getattr(settings, 'GS_PROJECT_ID', 'No configurado')
        print(f"✓ Bucket destino: {bucket_name}")
        print(f"✓ Project ID: {project_id}")
        print(f"✓ Media URL: {getattr(settings, 'MEDIA_URL', 'No configurado')}")
        return True
    else:
        print("⚠️  No está configurado Google Cloud Storage")
        print("    Las imágenes se guardarán localmente")
        return False

def main():
    """Ejecuta la migración completa de imágenes"""

    print("\n" + "="*60)
    print("🚀 MIGRACIÓN DE IMÁGENES A NUEVO BUCKET GCS")
    print("="*60)

    # Verificar configuración
    is_gcs = verify_current_configuration()

    if not is_gcs:
        response = input("\n¿Deseas continuar con almacenamiento local? (s/n): ")
        if response.lower() != 's':
            print("Migración cancelada.")
            return

    print("\n⚠️  ADVERTENCIA:")
    print("Este proceso descargará y re-subirá todas las imágenes.")
    print("Puede tomar varios minutos dependiendo de la cantidad de imágenes.")

    response = input("\n¿Deseas continuar? (s/n): ")
    if response.lower() != 's':
        print("Migración cancelada.")
        return

    # Contadores globales
    total_migrated = 0
    total_failed = 0
    total_skipped = 0
    total_no_image = 0

    # Lista de modelos a migrar con sus campos de imagen
    models_to_migrate = [
        (Servicio, 'imagen'),
        (Cabaña, 'imagen'),
        (Tina, 'imagen'),
        (Masaje, 'imagen'),
        (TipoCabaña, 'imagen'),
    ]

    # Migrar cada modelo
    for model_class, image_field in models_to_migrate:
        try:
            migrated, failed, skipped, no_image = migrate_model_images(
                model_class,
                image_field
            )
            total_migrated += migrated
            total_failed += failed
            total_skipped += skipped
            total_no_image += no_image
        except Exception as e:
            print(f"\n❌ Error migrando {model_class.__name__}: {e}")

    # Resumen final
    print("\n" + "="*60)
    print("📈 RESUMEN FINAL DE LA MIGRACIÓN")
    print("="*60)
    print(f"✅ Imágenes migradas: {total_migrated}")
    print(f"✓  Ya correctas: {total_skipped}")
    print(f"⚠️  Sin imagen: {total_no_image}")
    print(f"❌ Fallidas: {total_failed}")

    if total_migrated > 0:
        print("\n✨ Migración completada exitosamente!")
        print("\n📌 SIGUIENTES PASOS:")
        print("1. Verificar que las imágenes cargan en el sitio web")
        print("2. Probar subir una nueva imagen desde Django Admin")
        print("3. Verificar las Gift Cards muestran las imágenes correctamente")

        if total_failed > 0:
            print(f"\n⚠️  Nota: {total_failed} imágenes no pudieron migrarse.")
            print("   Revisa los logs para más detalles.")
    else:
        print("\nNo se migraron imágenes nuevas.")

if __name__ == "__main__":
    main()