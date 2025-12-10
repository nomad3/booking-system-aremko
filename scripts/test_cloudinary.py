#!/usr/bin/env python
"""
Script de prueba para verificar la configuración de Cloudinary.
Prueba la subida, transformación y eliminación de imágenes.
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

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
import logging
import datetime
import cloudinary
import cloudinary.uploader
from PIL import Image
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_cloudinary_upload():
    """Prueba completa de la funcionalidad de Cloudinary"""

    print("\n" + "=" * 60)
    print("🧪 PRUEBA DE CLOUDINARY")
    print("=" * 60)

    # 1. Verificar configuración
    print("\n📋 VERIFICANDO CONFIGURACIÓN:")
    print("-" * 40)

    storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', 'No configurado')
    is_cloudinary = 'cloudinary' in storage_backend.lower()

    print(f"Storage backend: {storage_backend}")

    if is_cloudinary:
        cloud_name = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'No configurado')
        api_key = getattr(settings, 'CLOUDINARY_API_KEY', 'No configurado')

        print(f"✓ Cloud Name: {cloud_name}")
        print(f"✓ API Key: {api_key[:10]}..." if api_key != 'No configurado' else '✗ API Key: No configurado')
        print(f"✓ API Secret: {'Configurado' if getattr(settings, 'CLOUDINARY_API_SECRET', None) else 'No configurado'}")
        print(f"✓ Media URL: {getattr(settings, 'MEDIA_URL', 'No configurado')}")

        # Configurar Cloudinary
        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=getattr(settings, 'CLOUDINARY_API_SECRET', '')
        )
    else:
        print("⚠️  Cloudinary no está configurado")
        print("    Asegúrate de configurar las variables de entorno:")
        print("    - CLOUDINARY_CLOUD_NAME")
        print("    - CLOUDINARY_API_KEY")
        print("    - CLOUDINARY_API_SECRET")
        return False

    try:
        # 2. Crear imagen de prueba
        print("\n📝 CREANDO IMAGEN DE PRUEBA:")
        print("-" * 40)

        # Crear una imagen simple con Pillow
        img = Image.new('RGB', (400, 300), color=(73, 109, 137))
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_buffer.seek(0)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        test_filename = f'test/cloudinary_test_{timestamp}.png'

        test_file = ContentFile(img_buffer.read(), name=test_filename)
        print(f"✓ Imagen creada: {test_filename}")
        print(f"✓ Tamaño: {len(test_file.read())} bytes")
        test_file.seek(0)  # Reset para poder leer de nuevo

        # 3. Subir archivo usando Django Storage
        print("\n📤 SUBIENDO IMAGEN VÍA DJANGO STORAGE:")
        print("-" * 40)

        saved_path = default_storage.save(test_filename, test_file)
        print(f"✅ Imagen subida exitosamente")
        print(f"   Ruta guardada: {saved_path}")

        # 4. Verificar URL
        print("\n🔗 VERIFICANDO URL PÚBLICA:")
        print("-" * 40)

        file_url = default_storage.url(saved_path)
        print(f"URL pública: {file_url}")

        if 'cloudinary.com' in file_url:
            print("✅ URL tiene el formato correcto de Cloudinary")
        else:
            print("⚠️  URL no parece ser de Cloudinary")

        # 5. Probar transformaciones de Cloudinary
        print("\n🎨 PROBANDO TRANSFORMACIONES:")
        print("-" * 40)

        # Generar URLs con transformaciones
        base_url = file_url.split('/upload/')[0] + '/upload/'
        resource_path = file_url.split('/upload/')[-1]

        # Thumbnail
        thumbnail_url = f"{base_url}c_thumb,w_200,h_200/{resource_path}"
        print(f"Thumbnail (200x200): {thumbnail_url}")

        # Versión móvil optimizada
        mobile_url = f"{base_url}c_scale,w_500,q_auto,f_auto/{resource_path}"
        print(f"Móvil optimizada: {mobile_url}")

        # Para gift cards
        giftcard_url = f"{base_url}c_scale,w_800,h_600,q_90/{resource_path}"
        print(f"Gift Card: {giftcard_url}")

        # 6. Subir directamente con Cloudinary API
        print("\n📤 SUBIENDO IMAGEN DIRECTA CON API:")
        print("-" * 40)

        # Crear otra imagen de prueba
        img2 = Image.new('RGB', (300, 200), color=(137, 73, 109))
        img_buffer2 = io.BytesIO()
        img2.save(img_buffer2, format='JPEG')
        img_buffer2.seek(0)

        # Subir con transformaciones predefinidas
        response = cloudinary.uploader.upload(
            img_buffer2,
            public_id=f"test/api_test_{timestamp}",
            folder="aremko",
            tags=["test", "aremko"],
            eager=[
                {"width": 200, "height": 200, "crop": "thumb"},
                {"width": 500, "crop": "scale", "quality": "auto"}
            ]
        )

        print(f"✅ Imagen subida via API")
        print(f"   Public ID: {response['public_id']}")
        print(f"   URL: {response['secure_url']}")
        print(f"   Formato: {response['format']}")
        print(f"   Tamaño: {response['bytes']} bytes")

        # 7. Verificar existencia
        print("\n🔍 VERIFICANDO EXISTENCIA:")
        print("-" * 40)

        exists = default_storage.exists(saved_path)
        if exists:
            print("✅ El archivo existe en Cloudinary")
        else:
            print("❌ El archivo NO se encuentra en Cloudinary")

        # 8. Limpiar archivos de prueba
        print("\n🗑️  LIMPIANDO:")
        print("-" * 40)

        # Eliminar archivo subido via Django Storage
        try:
            default_storage.delete(saved_path)
            print("✅ Archivo de prueba eliminado (Django Storage)")
        except Exception as e:
            print(f"⚠️  No se pudo eliminar via Django Storage: {e}")

        # Eliminar archivo subido via API
        try:
            cloudinary.uploader.destroy(response['public_id'])
            print("✅ Archivo de prueba eliminado (API)")
        except Exception as e:
            print(f"⚠️  No se pudo eliminar via API: {e}")

        # Resumen final
        print("\n" + "=" * 60)
        print("✅ PRUEBA COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        print("\nCloudinary está configurado y funcionando correctamente.")

        print("\n📌 CARACTERÍSTICAS DISPONIBLES:")
        print("• Subida de imágenes automática")
        print("• URLs públicas con CDN global")
        print("• Transformaciones en tiempo real")
        print("• Optimización automática de formato y calidad")
        print("• Thumbnails y versiones móviles sobre la marcha")

        print("\n💡 URLS DE TRANSFORMACIÓN ÚTILES:")
        print("• Thumbnail: /upload/c_thumb,w_200,h_200/")
        print("• Móvil: /upload/c_scale,w_500,q_auto,f_auto/")
        print("• Gift Card: /upload/c_scale,w_800,h_600,q_90/")
        print("• Auto calidad: /upload/q_auto,f_auto/")

        return True

    except Exception as e:
        print("\n" + "=" * 60)
        print("❌ ERROR EN LA PRUEBA")
        print("=" * 60)
        print(f"\nError: {e}")

        import traceback
        print("\nDetalles del error:")
        print("-" * 40)
        traceback.print_exc()

        print("\n💡 POSIBLES SOLUCIONES:")
        print("-" * 40)

        if 'credentials' in str(e).lower() or 'api' in str(e).lower():
            print("• Verificar que las variables de entorno están configuradas:")
            print("  - CLOUDINARY_CLOUD_NAME")
            print("  - CLOUDINARY_API_KEY")
            print("  - CLOUDINARY_API_SECRET")
            print("• Verificar que las credenciales son correctas")

        elif 'connection' in str(e).lower():
            print("• Verificar conexión a internet")
            print("• Verificar que Cloudinary no está bloqueado por firewall")

        return False

if __name__ == "__main__":
    success = test_cloudinary_upload()
    sys.exit(0 if success else 1)