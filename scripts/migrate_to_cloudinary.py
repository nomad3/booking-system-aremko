#!/usr/bin/env python
"""
Script para migrar imágenes existentes a Cloudinary.
Migra desde Google Cloud Storage o almacenamiento local.
"""

import os
import sys
import django
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio, CategoriaServicio, GiftCard
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
import requests
import cloudinary
import cloudinary.uploader
import logging
from urllib.parse import urlparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_cloudinary():
    """Configura Cloudinary con las credenciales"""
    cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', None)
    api_key = getattr(settings, 'CLOUDINARY_API_KEY', None)
    api_secret = getattr(settings, 'CLOUDINARY_API_SECRET', None)

    if not all([cloud_name, api_key, api_secret]):
        print("❌ Cloudinary no está configurado correctamente")
        print("   Asegúrate de configurar las variables de entorno:")
        print("   - CLOUDINARY_CLOUD_NAME")
        print("   - CLOUDINARY_API_KEY")
        print("   - CLOUDINARY_API_SECRET")
        return False

    cloudinary.config(
        cloud_name=cloud_name,
        api_key=api_key,
        api_secret=api_secret
    )

    print(f"✅ Cloudinary configurado: {cloud_name}")
    return True

def download_image(url):
    """Descarga una imagen desde una URL"""
    try:
        # Si es una URL relativa, construir la URL completa
        if url.startswith('/'):
            base_url = "https://aremko.cl"  # O el dominio que uses
            url = base_url + url

        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            return response.content
        else:
            logger.error(f"Error {response.status_code} descargando: {url}")
            return None
    except Exception as e:
        logger.error(f"Error descargando {url}: {e}")
        return None

def migrate_model_images(model_class, image_field='imagen'):
    """Migra imágenes de un modelo a Cloudinary"""

    model_name = model_class.__name__
    print(f"\n{'='*50}")
    print(f"📦 Migrando imágenes de: {model_name}")
    print(f"{'='*50}")

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

            # Verificar si ya está en Cloudinary
            if 'cloudinary.com' in current_url:
                print(f"  [{i}/{total}] ✓ {obj}: Ya en Cloudinary")
                skipped += 1
                continue

            # Determinar el tipo de migración necesaria
            is_gcs = 'storage.googleapis.com' in current_url or 'googleusercontent.com' in current_url
            is_local = current_url.startswith('/media/') or not current_url.startswith('http')

            print(f"  [{i}/{total}] 🔄 {obj}: Migrando...")
            print(f"      Desde: {current_url[:60]}...")

            # Preparar la imagen para subir
            image_content = None
            filename = os.path.basename(urlparse(current_url).path) or f"{model_name.lower()}_{obj.pk}.jpg"

            if is_gcs or current_url.startswith('http'):
                # Descargar desde URL externa
                image_content = download_image(current_url)
            elif is_local and hasattr(image, 'read'):
                # Leer desde archivo local
                try:
                    image.open('rb')
                    image_content = image.read()
                    image.close()
                except Exception as e:
                    print(f"      ⚠️ No se pudo leer archivo local: {e}")

            if image_content:
                # Subir a Cloudinary con optimizaciones
                try:
                    # Determinar carpeta según el modelo
                    folder_map = {
                        'Servicio': 'servicios',
                        'CategoriaServicio': 'categorias',
                        'GiftCard': 'giftcards'
                    }
                    folder = folder_map.get(model_name, 'general')

                    # Subir con transformaciones predefinidas
                    upload_result = cloudinary.uploader.upload(
                        image_content,
                        public_id=f"{folder}/{obj.pk}_{filename.split('.')[0]}",
                        folder=f"aremko/{folder}",
                        tags=[model_name.lower(), "migrado"],
                        overwrite=True,
                        resource_type="image",
                        eager=[
                            # Thumbnail para listas
                            {"width": 200, "height": 200, "crop": "thumb", "gravity": "center"},
                            # Versión móvil
                            {"width": 500, "crop": "scale", "quality": "auto", "fetch_format": "auto"},
                            # Versión para gift cards
                            {"width": 800, "height": 600, "crop": "fit", "quality": 90}
                        ],
                        eager_async=True  # Generar transformaciones en background
                    )

                    # Actualizar el campo de imagen con la nueva URL
                    # Guardamos solo el public_id para que Django-Cloudinary lo maneje
                    from django.core.files.base import ContentFile

                    # Crear un archivo temporal con el contenido
                    temp_file = ContentFile(image_content, name=filename)

                    # Guardar usando el storage de Django (que ahora es Cloudinary)
                    image.save(filename, temp_file, save=True)

                    print(f"      ✅ Migrado exitosamente")
                    print(f"      Nueva URL: {upload_result['secure_url'][:60]}...")
                    print(f"      Public ID: {upload_result['public_id']}")
                    migrated += 1

                except Exception as e:
                    print(f"      ❌ Error subiendo a Cloudinary: {e}")
                    failed += 1
            else:
                print(f"      ❌ No se pudo obtener el contenido de la imagen")
                failed += 1

        except Exception as e:
            print(f"  [{i}/{total}] ❌ {obj}: Error - {e}")
            failed += 1

    # Resumen del modelo
    print(f"\n📊 Resumen {model_name}:")
    print(f"  • Total procesados: {total}")
    print(f"  • Sin imagen: {no_image}")
    print(f"  • Migradas: {migrated}")
    print(f"  • Ya en Cloudinary: {skipped}")
    print(f"  • Fallidas: {failed}")

    return migrated, failed, skipped, no_image

def verify_cloudinary_configuration():
    """Verifica la configuración de Cloudinary"""
    print("\n" + "="*60)
    print("🔍 VERIFICANDO CONFIGURACIÓN DE CLOUDINARY")
    print("="*60)

    storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', 'No configurado')
    is_cloudinary = 'cloudinary' in storage_backend.lower()

    print(f"Backend: {storage_backend}")

    if is_cloudinary:
        cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'No configurado')
        print(f"✓ Cloud Name: {cloud_name}")
        print(f"✓ Media URL: {getattr(settings, 'MEDIA_URL', 'No configurado')}")
        return True
    else:
        print("⚠️  Cloudinary no está configurado como storage principal")
        print("    El sistema está usando: " + storage_backend)
        return False

def main():
    """Ejecuta la migración completa a Cloudinary"""

    print("\n" + "="*60)
    print("🚀 MIGRACIÓN DE IMÁGENES A CLOUDINARY")
    print("="*60)

    # Verificar y configurar Cloudinary
    if not setup_cloudinary():
        print("\n❌ No se puede continuar sin configuración de Cloudinary")
        return

    # Verificar configuración de Django
    if not verify_cloudinary_configuration():
        response = input("\n¿Deseas continuar de todos modos? (s/n): ")
        if response.lower() != 's':
            print("Migración cancelada.")
            return

    print("\n⚠️  ADVERTENCIA:")
    print("Este proceso migrará todas las imágenes a Cloudinary.")
    print("Las imágenes se optimizarán automáticamente para web.")
    print("Se generarán versiones thumbnail y móvil.")

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
        (CategoriaServicio, 'imagen'),
        (GiftCard, 'imagen'),
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
    print(f"✓  Ya en Cloudinary: {total_skipped}")
    print(f"⚠️  Sin imagen: {total_no_image}")
    print(f"❌ Fallidas: {total_failed}")

    if total_migrated > 0:
        print("\n✨ Migración completada!")
        print("\n🎨 BENEFICIOS ACTIVADOS:")
        print("• CDN global para carga rápida")
        print("• Optimización automática de formato (WebP/AVIF)")
        print("• Transformaciones en tiempo real")
        print("• Thumbnails generados automáticamente")
        print("• Versiones móviles optimizadas")

        print("\n📌 SIGUIENTES PASOS:")
        print("1. Verificar que las imágenes cargan en el sitio web")
        print("2. Probar subir una nueva imagen desde Django Admin")
        print("3. Verificar las Gift Cards con las nuevas URLs")
        print("4. Revisar el dashboard de Cloudinary para ver las estadísticas")

        if total_failed > 0:
            print(f"\n⚠️  Nota: {total_failed} imágenes no pudieron migrarse.")
            print("   Revisa los logs para más detalles.")
    else:
        print("\nNo se migraron imágenes nuevas.")
        if total_skipped > 0:
            print(f"Las {total_skipped} imágenes ya estaban en Cloudinary.")

if __name__ == "__main__":
    main()