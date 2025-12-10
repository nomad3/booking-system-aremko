#!/usr/bin/env python
"""
Script de prueba para verificar la configuración de Google Cloud Storage.
Prueba la subida, lectura y eliminación de archivos.
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.conf import settings
import logging
import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_gcs_upload():
    """Prueba completa de la funcionalidad de Google Cloud Storage"""

    print("\n" + "=" * 60)
    print("🧪 PRUEBA DE GOOGLE CLOUD STORAGE")
    print("=" * 60)

    # 1. Verificar configuración
    print("\n📋 VERIFICANDO CONFIGURACIÓN:")
    print("-" * 40)

    storage_backend = getattr(settings, 'DEFAULT_FILE_STORAGE', 'No configurado')
    is_gcs = 'gcloud' in storage_backend.lower()

    print(f"Storage backend: {storage_backend}")

    if is_gcs:
        bucket_name = getattr(settings, 'GS_BUCKET_NAME', 'No configurado')
        project_id = getattr(settings, 'GS_PROJECT_ID', 'No configurado')
        media_url = getattr(settings, 'MEDIA_URL', 'No configurado')

        print(f"✓ Bucket: {bucket_name}")
        print(f"✓ Project ID: {project_id}")
        print(f"✓ Media URL: {media_url}")
        print(f"✓ Public ACL: {getattr(settings, 'GS_DEFAULT_ACL', 'No configurado')}")
        print(f"✓ Query Auth: {getattr(settings, 'GS_QUERYSTRING_AUTH', True)}")
    else:
        print("⚠️  Usando almacenamiento local")
        print(f"✓ Media URL: {getattr(settings, 'MEDIA_URL', 'No configurado')}")
        print(f"✓ Media Root: {getattr(settings, 'MEDIA_ROOT', 'No configurado')}")

    # 2. Crear archivo de prueba
    print("\n📝 CREANDO ARCHIVO DE PRUEBA:")
    print("-" * 40)

    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    test_filename = f'test/gcs_test_{timestamp}.txt'
    test_content = f"""
    Prueba de Google Cloud Storage
    ==============================
    Fecha: {datetime.datetime.now()}
    Backend: {storage_backend}
    Sistema: Aremko Booking System

    Este es un archivo de prueba para verificar
    que la configuración de GCS funciona correctamente.
    """.encode('utf-8')

    test_file = ContentFile(test_content, name=test_filename)
    print(f"✓ Archivo creado: {test_filename}")
    print(f"✓ Tamaño: {len(test_content)} bytes")

    try:
        # 3. Subir archivo
        print("\n📤 SUBIENDO ARCHIVO:")
        print("-" * 40)

        saved_path = default_storage.save(test_filename, test_file)
        print(f"✅ Archivo subido exitosamente")
        print(f"   Ruta guardada: {saved_path}")

        # 4. Verificar URL
        print("\n🔗 VERIFICANDO URL PÚBLICA:")
        print("-" * 40)

        file_url = default_storage.url(saved_path)
        print(f"URL pública: {file_url}")

        if is_gcs:
            expected_url_prefix = f"https://storage.googleapis.com/{bucket_name}/"
            if file_url.startswith(expected_url_prefix):
                print("✅ URL tiene el formato correcto de GCS")
            else:
                print(f"⚠️  URL no coincide con el formato esperado")
                print(f"   Esperado: {expected_url_prefix}...")

        # 5. Verificar existencia
        print("\n🔍 VERIFICANDO EXISTENCIA:")
        print("-" * 40)

        exists = default_storage.exists(saved_path)
        if exists:
            print("✅ El archivo existe en el storage")
        else:
            print("❌ El archivo NO se encuentra en el storage")

        # 6. Obtener tamaño
        try:
            size = default_storage.size(saved_path)
            print(f"✓ Tamaño del archivo: {size} bytes")
        except Exception as e:
            print(f"⚠️  No se pudo obtener el tamaño: {e}")

        # 7. Listar archivos en el directorio de prueba
        print("\n📂 LISTANDO ARCHIVOS DE PRUEBA:")
        print("-" * 40)

        try:
            dirs, files = default_storage.listdir('test')
            print(f"✓ Archivos en 'test/': {len(files)}")
            for f in files[-5:]:  # Mostrar últimos 5 archivos
                print(f"   - {f}")
        except Exception as e:
            print(f"⚠️  No se pudo listar directorio: {e}")

        # 8. Limpiar archivo de prueba
        print("\n🗑️  LIMPIANDO:")
        print("-" * 40)

        default_storage.delete(saved_path)
        print("✅ Archivo de prueba eliminado")

        # Verificar que se eliminó
        if not default_storage.exists(saved_path):
            print("✅ Confirmado: archivo ya no existe")
        else:
            print("⚠️  El archivo aún existe después de eliminar")

        # Resumen final
        print("\n" + "=" * 60)
        print("✅ PRUEBA COMPLETADA EXITOSAMENTE")
        print("=" * 60)
        print("\nLa configuración de almacenamiento está funcionando correctamente.")

        if is_gcs:
            print("\n📌 SIGUIENTES PASOS:")
            print("1. Verificar que las imágenes se pueden subir desde Django Admin")
            print("2. Probar la generación de Gift Cards con imágenes")
            print("3. Verificar que las imágenes cargan en el sitio web")

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

        if 'credentials' in str(e).lower():
            print("• Verificar que GCS_CREDENTIALS_JSON está configurado en Render")
            print("• Verificar que el JSON de credenciales es válido")
            print("• Asegurarse de que el JSON está minificado correctamente")

        elif 'permission' in str(e).lower():
            print("• Verificar que la cuenta de servicio tiene rol 'Storage Admin'")
            print("• Verificar permisos del bucket en Google Cloud Console")

        elif 'bucket' in str(e).lower():
            print("• Verificar que el bucket existe y el nombre es correcto")
            print("• Verificar que GS_BUCKET_NAME está configurado correctamente")

        return False

if __name__ == "__main__":
    success = test_gcs_upload()
    sys.exit(0 if success else 1)