#!/usr/bin/env python
"""
Script para subir imágenes de la página de empresas a Cloudinary

INSTRUCCIONES:
1. Coloca las siguientes imágenes en el directorio temp_images_empresas/:
   - desayuno_empresas_aremko.jpg
   - 4_amigas_en_la_calbuco.PNG
   - charla_empresas_aremko.jpg

2. Asegúrate de tener las variables de entorno configuradas:
   - CLOUDINARY_CLOUD_NAME
   - CLOUDINARY_API_KEY
   - CLOUDINARY_API_SECRET

3. Ejecuta este script:
   python scripts/upload_empresas_images_to_cloudinary.py

Las imágenes se subirán a la carpeta 'categorias' en Cloudinary.
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

import cloudinary
import cloudinary.uploader
from django.conf import settings

print("=" * 80)
print("SUBIR IMÁGENES DE EMPRESAS A CLOUDINARY")
print("=" * 80)

# Verificar configuración de Cloudinary
if not all([settings.CLOUDINARY_CLOUD_NAME, settings.CLOUDINARY_API_KEY, settings.CLOUDINARY_API_SECRET]):
    print("❌ ERROR: Cloudinary no está configurado correctamente")
    print("   Asegúrate de tener las variables de entorno:")
    print("   - CLOUDINARY_CLOUD_NAME")
    print("   - CLOUDINARY_API_KEY")
    print("   - CLOUDINARY_API_SECRET")
    sys.exit(1)

# Configurar Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

# Directorio de imágenes temporales
TEMP_DIR = BASE_DIR / 'temp_images_empresas'

# Imágenes a subir
IMAGES = [
    'desayuno_empresas_aremko.jpg',
    '4_amigas_en_la_calbuco.PNG',
    'charla_empresas_aremko.jpg'
]

print(f"\n📁 Buscando imágenes en: {TEMP_DIR}")
print("-" * 80)

uploaded_urls = {}

for image_name in IMAGES:
    image_path = TEMP_DIR / image_name

    if not image_path.exists():
        print(f"⚠️  {image_name} - NO ENCONTRADA")
        print(f"   Por favor, coloca esta imagen en: {TEMP_DIR}/")
        continue

    print(f"\n📤 Subiendo: {image_name}")

    try:
        # Subir a Cloudinary en la carpeta 'categorias'
        public_id = f"categorias/{image_name.rsplit('.', 1)[0]}"

        result = cloudinary.uploader.upload(
            str(image_path),
            public_id=public_id,
            folder='categorias',
            overwrite=True,
            resource_type='image'
        )

        url = result['secure_url']
        uploaded_urls[image_name] = url

        print(f"✅ Subida exitosa")
        print(f"   URL: {url}")
        print(f"   Public ID: {result['public_id']}")
        print(f"   Tamaño: {result.get('bytes', 0) / 1024:.1f} KB")

    except Exception as e:
        print(f"❌ Error subiendo {image_name}: {str(e)}")

print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)

if uploaded_urls:
    print(f"\n✅ {len(uploaded_urls)} imagen(es) subida(s) exitosamente:\n")
    for name, url in uploaded_urls.items():
        print(f"   {name}")
        print(f"   → {url}\n")

    print("\n📝 Ahora ejecuta el siguiente comando para actualizar el template:")
    print("   python scripts/update_empresas_template_urls.py")
else:
    print("\n⚠️  No se subieron imágenes")
    print(f"\nAsegúrate de colocar las imágenes en: {TEMP_DIR}/")
    print("\nImágenes necesarias:")
    for img in IMAGES:
        print(f"   - {img}")

print("\n" + "=" * 80)
