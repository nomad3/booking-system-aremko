#!/usr/bin/env python3
"""
Script simplificado para subir imágenes de categorías a Cloudinary
"""

import os
import sys
from pathlib import Path

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    print("❌ Error: El módulo 'cloudinary' no está instalado")
    sys.exit(1)

print("=" * 80)
print("SUBIR IMÁGENES DE CATEGORÍAS A CLOUDINARY")
print("=" * 80)

# Obtener credenciales de variables de entorno
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
BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / 'temp_images_empresas'

# Mapeo: nombre base del archivo -> descripción
CATEGORY_IMAGES = {
    'tinas_hero': 'Tinas Calientes',
    'masajes_hero': 'Masajes',
    'alojamientos_hero': 'Alojamientos/Cabañas',
}

print(f"\n📁 Buscando imágenes en: {TEMP_DIR}")
print("-" * 80)

uploaded = []

for image_base, descripcion in CATEGORY_IMAGES.items():
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

    print(f"\n📤 Subiendo: {image_path.name} ({descripcion})")

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
        print(f"   🆔 Public ID: {result['public_id']}")
        print(f"   📦 Tamaño: {result.get('bytes', 0) / 1024 / 1024:.2f} MB")
        print(f"   🖼️  Dimensiones: {result.get('width')}x{result.get('height')}")

        uploaded.append({
            'nombre': descripcion,
            'url': url,
            'file': image_path.name,
            'public_id': result['public_id']
        })

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)

if uploaded:
    print(f"\n✅ {len(uploaded)} imagen(es) subida(s) exitosamente:\n")

    for item in uploaded:
        print(f"📸 {item['nombre']}")
        print(f"   Archivo: {item['file']}")
        print(f"   URL: {item['url']}")
        print(f"   Public ID: {item['public_id']}\n")

    print("\n" + "=" * 80)
    print("PRÓXIMO PASO: Actualizar categorías en la base de datos")
    print("=" * 80)
    print("\nEjecuta en el shell de producción (Render):")
    print("\nfrom ventas.models import CategoriaServicio")

    for item in uploaded:
        categoria_id = {'Tinas Calientes': 1, 'Masajes': 2, 'Alojamientos/Cabañas': 3}[item['nombre']]
        print(f"\n# {item['nombre']}")
        print(f"cat = CategoriaServicio.objects.get(id={categoria_id})")
        print(f"cat.imagen = '{item['public_id']}'")
        print(f"cat.save()")

else:
    print("\n⚠️  No se subieron imágenes")
    print(f"\nColoca las siguientes imágenes en: {TEMP_DIR}/\n")
    print("   - tinas_hero.jpg (para /tinas/)")
    print("   - masajes_hero.jpg (para /masajes/)")
    print("   - alojamientos_hero.jpg (para /alojamientos/)")

print("\n" + "=" * 80)
