#!/usr/bin/env python3
"""
Script para subir imágenes de categorías (Tinas, Masajes, Alojamientos) a Cloudinary
y actualizar las categorías en la base de datos
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

from ventas.models import CategoriaServicio
import cloudinary
import cloudinary.uploader
from django.conf import settings

print("=" * 80)
print("SUBIR IMÁGENES DE CATEGORÍAS A CLOUDINARY")
print("=" * 80)

# Verificar configuración de Cloudinary
CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
API_KEY = os.getenv('CLOUDINARY_API_KEY')
API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

if not all([CLOUD_NAME, API_KEY, API_SECRET]):
    print("\n❌ ERROR: Cloudinary no está configurado")
    print("\nEjecuta primero:")
    print("   export CLOUDINARY_CLOUD_NAME='dtuncr1pi'")
    print("   export CLOUDINARY_API_KEY='493892349837672'")
    print("   export CLOUDINARY_API_SECRET='1hVjcgm4qR87iMKUc-MLN5CPz3U'")
    sys.exit(1)

# Configurar Cloudinary
cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET,
    secure=True
)

print(f"\n✅ Cloudinary configurado: {CLOUD_NAME}")

# Directorio de imágenes
TEMP_DIR = BASE_DIR / 'temp_images_empresas'

# Mapeo: nombre base del archivo -> ID de categoría
CATEGORY_IMAGES = {
    'tinas_hero': 1,  # Tinas Calientes
    'masajes_hero': 2,  # Masajes
    'alojamientos_hero': 3,  # Alojamientos/Cabañas
}

print(f"\n📁 Buscando imágenes en: {TEMP_DIR}")
print("-" * 80)

uploaded = []

for image_base, categoria_id in CATEGORY_IMAGES.items():
    # Buscar el archivo con diferentes extensiones
    possible_extensions = ['.jpg', '.JPG', '.png', '.PNG', '.jpeg', '.JPEG']
    image_path = None

    for ext in possible_extensions:
        path = TEMP_DIR / f"{image_base}{ext}"
        if path.exists():
            image_path = path
            break

    if not image_path:
        print(f"\n⚠️  {image_base} - NO ENCONTRADA")
        print(f"   Coloca la imagen en: {TEMP_DIR}/{image_base}.jpg")
        continue

    print(f"\n📤 Subiendo: {image_path.name}")

    try:
        # Subir a Cloudinary
        public_id = f"categorias/{image_base}"

        result = cloudinary.uploader.upload(
            str(image_path),
            public_id=public_id,
            overwrite=True,
            resource_type='image'
        )

        url = result['secure_url']

        print(f"   ✅ Subida exitosa a Cloudinary")
        print(f"   📍 URL: {url}")

        # Actualizar categoría en base de datos
        try:
            categoria = CategoriaServicio.objects.get(id=categoria_id)
            # Guardar solo el public_id de Cloudinary
            categoria.imagen = f"{public_id}.{result['format']}"
            categoria.save()

            print(f"   ✅ Categoría actualizada: {categoria.nombre}")
            uploaded.append({
                'nombre': categoria.nombre,
                'url': url,
                'file': image_path.name
            })

        except CategoriaServicio.DoesNotExist:
            print(f"   ⚠️  Categoría con ID {categoria_id} no encontrada en BD")

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")

print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)

if uploaded:
    print(f"\n✅ {len(uploaded)} imagen(es) subida(s) y categoría(s) actualizada(s):\n")

    for item in uploaded:
        print(f"📸 {item['nombre']}")
        print(f"   Archivo: {item['file']}")
        print(f"   URL: {item['url']}\n")

    print("✅ Las imágenes ya están configuradas en las categorías")
    print("✅ Verifica en la web: /tinas/, /masajes/, /alojamientos/")

else:
    print("\n⚠️  No se subieron imágenes")
    print(f"\nColoca las siguientes imágenes en: {TEMP_DIR}/\n")
    print("   - tinas_hero.jpg (para /tinas/)")
    print("   - masajes_hero.jpg (para /masajes/)")
    print("   - alojamientos_hero.jpg (para /alojamientos/)")

print("\n" + "=" * 80)
