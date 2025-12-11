#!/usr/bin/env python3
"""
Script simplificado para subir imágenes a Cloudinary sin depender de Django
"""

import os
import sys
from pathlib import Path

try:
    import cloudinary
    import cloudinary.uploader
except ImportError:
    print("❌ Error: El módulo 'cloudinary' no está instalado")
    print("   Instala con: pip install cloudinary")
    sys.exit(1)

print("=" * 80)
print("SUBIR IMÁGENES DE EMPRESAS A CLOUDINARY")
print("=" * 80)

# Obtener credenciales de variables de entorno
CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME')
API_KEY = os.getenv('CLOUDINARY_API_KEY')
API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

# Verificar configuración
if not all([CLOUD_NAME, API_KEY, API_SECRET]):
    print("\n❌ ERROR: Cloudinary no está configurado correctamente")
    print("\nAsegúrate de tener las variables de entorno:")
    print("   export CLOUDINARY_CLOUD_NAME='tu_cloud_name'")
    print("   export CLOUDINARY_API_KEY='tu_api_key'")
    print("   export CLOUDINARY_API_SECRET='tu_api_secret'")
    print("\nValores actuales:")
    print(f"   CLOUDINARY_CLOUD_NAME: {'✅ Configurado' if CLOUD_NAME else '❌ No configurado'}")
    print(f"   CLOUDINARY_API_KEY: {'✅ Configurado' if API_KEY else '❌ No configurado'}")
    print(f"   CLOUDINARY_API_SECRET: {'✅ Configurado' if API_SECRET else '❌ No configurado'}")
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

# Imágenes a subir
IMAGES_BASE = [
    'desayuno_empresas_aremko',
    '4_amigas_en_la_calbuco',
    'charla_empresas_aremko'
]

print(f"\n📁 Buscando imágenes en: {TEMP_DIR}")
print("-" * 80)

uploaded_urls = {}

for image_base in IMAGES_BASE:
    # Buscar el archivo con diferentes extensiones
    possible_extensions = ['.jpg', '.JPG', '.png', '.PNG', '.jpeg', '.JPEG']
    image_path = None

    for ext in possible_extensions:
        path = TEMP_DIR / f"{image_base}{ext}"
        if path.exists():
            image_path = path
            break

    if not image_path:
        print(f"⚠️  {image_base} - NO ENCONTRADA")
        print(f"   Buscando: {image_base}{{.jpg,.JPG,.png,.PNG}}")
        continue

    print(f"\n📤 Subiendo: {image_path.name}")

    try:
        # Subir a Cloudinary en la carpeta 'categorias'
        public_id = f"categorias/{image_base}"

        result = cloudinary.uploader.upload(
            str(image_path),
            public_id=public_id,
            overwrite=True,
            resource_type='image'
        )

        url = result['secure_url']
        uploaded_urls[image_path.name] = url

        print(f"   ✅ Subida exitosa")
        print(f"   📍 URL: {url}")
        print(f"   🆔 Public ID: {result['public_id']}")
        print(f"   📦 Tamaño: {result.get('bytes', 0) / 1024:.1f} KB")
        print(f"   🖼️  Dimensiones: {result.get('width')}x{result.get('height')}")

    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 80)
print("RESUMEN")
print("=" * 80)

if uploaded_urls:
    print(f"\n✅ {len(uploaded_urls)} imagen(es) subida(s) exitosamente:\n")

    for name, url in uploaded_urls.items():
        print(f"📸 {name}")
        print(f"   {url}\n")

    print("\n" + "=" * 80)
    print("PRÓXIMO PASO: Actualizar template")
    print("=" * 80)
    print("\nCopia estas URLs en ventas/templates/ventas/empresas.html")
    print("Reemplaza las URLs de Unsplash con estas de Cloudinary\n")

else:
    print("\n⚠️  No se subieron imágenes")
    print(f"\nVerifica que las imágenes estén en: {TEMP_DIR}/")

print("=" * 80)
