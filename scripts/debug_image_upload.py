#!/usr/bin/env python
"""
Script para debuggear el problema de subida de imágenes con error 500.
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
import logging

# Configurar logging detallado
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

print("=" * 60)
print("DEBUG: CONFIGURACIÓN DE IMAGEN UPLOAD")
print("=" * 60)

# 1. Verificar configuración básica
print("\n📋 CONFIGURACIÓN BÁSICA:")
print("-" * 40)
print(f"DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")
print(f"MEDIA_ROOT: {getattr(settings, 'MEDIA_ROOT', 'No configurado')}")

# 2. Verificar Cloudinary
print("\n☁️ CONFIGURACIÓN CLOUDINARY:")
print("-" * 40)
if hasattr(settings, 'CLOUDINARY_STORAGE'):
    for key, value in settings.CLOUDINARY_STORAGE.items():
        if key != 'API_SECRET':
            print(f"  {key}: {value}")
else:
    print("  CLOUDINARY_STORAGE: No configurado")

# 3. Verificar dependencias
print("\n📦 DEPENDENCIAS:")
print("-" * 40)

try:
    import cloudinary
    print(f"✅ cloudinary: {cloudinary.__version__ if hasattr(cloudinary, '__version__') else 'instalado'}")
except ImportError as e:
    print(f"❌ cloudinary: {e}")

try:
    import cloudinary_storage
    print(f"✅ cloudinary_storage: instalado")
except ImportError as e:
    print(f"❌ cloudinary_storage: {e}")

try:
    from PIL import Image
    import PIL
    print(f"✅ Pillow: {PIL.__version__}")
except ImportError as e:
    print(f"❌ Pillow: {e}")

# 4. Probar subida real
print("\n🧪 PRUEBA DE SUBIDA:")
print("-" * 40)

try:
    from django.core.files.uploadedfile import SimpleUploadedFile
    from ventas.models import Servicio
    from PIL import Image
    import io

    # Crear imagen de prueba
    img = Image.new('RGB', (100, 100), color='blue')
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    # Crear archivo de prueba
    test_file = SimpleUploadedFile(
        name='test_debug.png',
        content=img_buffer.getvalue(),
        content_type='image/png'
    )

    print(f"✓ Archivo de prueba creado: {len(test_file.read())} bytes")
    test_file.seek(0)

    # Intentar con el storage directamente
    from django.core.files.storage import default_storage

    print("Intentando guardar con default_storage...")
    try:
        path = default_storage.save('test/debug_test.png', test_file)
        print(f"✅ Archivo guardado: {path}")

        url = default_storage.url(path)
        print(f"📎 URL: {url}")

        # Limpiar
        default_storage.delete(path)
        print("✓ Archivo eliminado")

    except Exception as e:
        print(f"❌ Error con default_storage: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"❌ Error en prueba: {e}")
    import traceback
    traceback.print_exc()

# 5. Verificar el modelo Servicio
print("\n📊 VERIFICACIÓN DEL MODELO:")
print("-" * 40)

try:
    from ventas.models import Servicio

    # Obtener info del campo imagen
    imagen_field = Servicio._meta.get_field('imagen')
    print(f"Campo 'imagen' en Servicio:")
    print(f"  Tipo: {type(imagen_field).__name__}")
    print(f"  upload_to: {imagen_field.upload_to}")
    print(f"  blank: {imagen_field.blank}")
    print(f"  null: {imagen_field.null}")

    if hasattr(imagen_field, 'storage'):
        print(f"  storage: {imagen_field.storage}")

except Exception as e:
    print(f"❌ Error verificando modelo: {e}")

# 6. Verificar permisos y configuración de Cloudinary
print("\n🔐 VERIFICACIÓN DE API:")
print("-" * 40)

try:
    import cloudinary
    import cloudinary.api

    # Configurar con las variables de entorno
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET')
    )

    # Intentar obtener info
    result = cloudinary.api.ping()
    print(f"✅ Conexión a Cloudinary API exitosa")

except Exception as e:
    print(f"❌ Error con API de Cloudinary: {e}")

# 7. Sugerencias
print("\n💡 DIAGNÓSTICO:")
print("-" * 40)

issues = []

if 'cloudinary' not in settings.DEFAULT_FILE_STORAGE.lower():
    issues.append("Cloudinary no está configurado como DEFAULT_FILE_STORAGE")

if not os.getenv('CLOUDINARY_CLOUD_NAME'):
    issues.append("CLOUDINARY_CLOUD_NAME no está en variables de entorno")

if not os.getenv('CLOUDINARY_API_KEY'):
    issues.append("CLOUDINARY_API_KEY no está en variables de entorno")

if not os.getenv('CLOUDINARY_API_SECRET'):
    issues.append("CLOUDINARY_API_SECRET no está en variables de entorno")

try:
    from PIL import Image
except:
    issues.append("Pillow no está instalado o tiene problemas")

if issues:
    print("❌ Problemas encontrados:")
    for issue in issues:
        print(f"  - {issue}")
else:
    print("✅ La configuración parece correcta")
    print("\nSi aún hay error 500, el problema puede ser:")
    print("  1. Límite de tamaño de archivo")
    print("  2. Formato de imagen no soportado")
    print("  3. Timeout en la subida")
    print("  4. Problema con el formulario de Django Admin")
    print("\nRevisa los logs completos del error en Render.")

print("\n" + "=" * 60)