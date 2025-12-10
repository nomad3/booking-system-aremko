#!/usr/bin/env python
"""
Script para diagnosticar y arreglar problemas de subida de imágenes con Cloudinary.
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
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
import cloudinary

print("=" * 60)
print("DIAGNÓSTICO DE CLOUDINARY UPLOAD")
print("=" * 60)

# 1. Verificar configuración
print("\n📋 CONFIGURACIÓN:")
print("-" * 40)

print(f"DEFAULT_FILE_STORAGE: {settings.DEFAULT_FILE_STORAGE}")
print(f"MEDIA_URL: {settings.MEDIA_URL}")

if hasattr(settings, 'CLOUDINARY_STORAGE'):
    print(f"CLOUDINARY_STORAGE configurado: Sí")
    for key, value in settings.CLOUDINARY_STORAGE.items():
        if key != 'API_SECRET':
            print(f"  {key}: {value}")
else:
    print(f"CLOUDINARY_STORAGE configurado: No")

# 2. Probar subida directa
print("\n🧪 PRUEBA DE SUBIDA:")
print("-" * 40)

try:
    # Crear un archivo de prueba
    test_content = b"Test image content for Cloudinary"
    test_file = ContentFile(test_content, name='test/upload_test.txt')

    # Intentar guardar
    print("Intentando guardar archivo de prueba...")
    saved_path = default_storage.save('test/upload_test.txt', test_file)
    print(f"✅ Archivo guardado: {saved_path}")

    # Obtener URL
    url = default_storage.url(saved_path)
    print(f"📎 URL: {url}")

    # Verificar existencia
    exists = default_storage.exists(saved_path)
    print(f"✓ Existe: {exists}")

    # Limpiar
    default_storage.delete(saved_path)
    print("✓ Archivo de prueba eliminado")

except Exception as e:
    print(f"❌ Error en prueba de subida: {e}")
    import traceback
    traceback.print_exc()

# 3. Verificar permisos de Cloudinary
print("\n🔐 VERIFICANDO PERMISOS:")
print("-" * 40)

try:
    import cloudinary.api

    # Obtener información de uso
    usage = cloudinary.api.usage()
    print(f"✅ Conexión exitosa a Cloudinary")
    print(f"  Plan: {usage.get('plan', 'N/A')}")
    print(f"  Créditos usados: {usage.get('credits', {}).get('usage', 'N/A')}")
    print(f"  Límite: {usage.get('credits', {}).get('limit', 'N/A')}")

except Exception as e:
    print(f"❌ Error verificando permisos: {e}")

# 4. Probar con un modelo real
print("\n📦 PRUEBA CON MODELO:")
print("-" * 40)

try:
    from ventas.models import Servicio
    from PIL import Image
    import io

    # Crear una imagen de prueba real
    img = Image.new('RGB', (100, 100), color='red')
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    # Obtener un servicio de prueba
    servicio = Servicio.objects.first()
    if servicio:
        print(f"Servicio de prueba: {servicio.nombre}")

        # Guardar imagen temporal
        from django.core.files.uploadedfile import SimpleUploadedFile
        test_image = SimpleUploadedFile(
            name='test_image.png',
            content=img_buffer.getvalue(),
            content_type='image/png'
        )

        # Intentar asignar la imagen
        print("Intentando asignar imagen al servicio...")
        old_image = servicio.imagen
        servicio.imagen = test_image

        # NO guardar realmente, solo simular
        print("✅ Asignación de imagen funciona correctamente")

        # Restaurar imagen original
        servicio.imagen = old_image
        print("✓ Imagen original restaurada (sin cambios en BD)")

    else:
        print("⚠️ No hay servicios para probar")

except Exception as e:
    print(f"❌ Error con modelo: {e}")
    import traceback
    traceback.print_exc()

# 5. Recomendaciones
print("\n💡 RECOMENDACIONES:")
print("-" * 40)

if 'cloudinary' in settings.DEFAULT_FILE_STORAGE.lower():
    print("✅ Cloudinary está configurado como storage")
    print("\nSi hay error 500 al subir:")
    print("1. Verificar que las apps están en el orden correcto en INSTALLED_APPS")
    print("2. Verificar que no hay conflictos con django-storages")
    print("3. Revisar logs de Render para el error específico")
    print("4. Asegurarse de que Pillow está instalado correctamente")
else:
    print("❌ Cloudinary NO está configurado como storage principal")
    print("Verificar variables de entorno en Render")

print("\n" + "=" * 60)