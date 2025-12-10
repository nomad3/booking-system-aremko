#!/usr/bin/env python
"""
Script para re-subir todas las imágenes a Cloudinary correctamente.
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

from ventas.models import Servicio
from django.conf import settings
import cloudinary
import cloudinary.uploader
import requests

print("=" * 60)
print("RE-SUBIR IMÁGENES A CLOUDINARY")
print("=" * 60)

# Configurar Cloudinary
CLOUD_NAME = os.getenv('CLOUDINARY_CLOUD_NAME', 'dtuncr1pi')
API_KEY = os.getenv('CLOUDINARY_API_KEY')
API_SECRET = os.getenv('CLOUDINARY_API_SECRET')

cloudinary.config(
    cloud_name=CLOUD_NAME,
    api_key=API_KEY,
    api_secret=API_SECRET
)

print(f"\nCloud Name: {CLOUD_NAME}")
print("-" * 40)

# Lista de imágenes conocidas con sus URLs originales (de donde sea que estén)
KNOWN_IMAGES = {
    'Cabaña Tepa': 'https://res.cloudinary.com/dtuncr1pi/servicios/Tepa_3.jpg',
    'Masaje Relajación o Descontracturante': 'https://res.cloudinary.com/dtuncr1pi/servicios/masajepara2.jpg',
    'Tina Hidromasaje Villarrica': 'https://res.cloudinary.com/dtuncr1pi/servicios/tina_villarrica.jpeg',
    'Tina Hidromasaje Llaima': 'https://res.cloudinary.com/dtuncr1pi/servicios/llaima_foto.jpeg',
    'Tina Tronador': 'https://res.cloudinary.com/dtuncr1pi/servicios/tronador1.jpeg',
    'Tina Hornopiren': 'https://res.cloudinary.com/dtuncr1pi/servicios/hornopirenmama.jpg',
    'Tina Osorno': 'https://res.cloudinary.com/dtuncr1pi/servicios/amigasosorno.jpg',
    'Tina Hidromasaje Puyehue': 'https://res.cloudinary.com/dtuncr1pi/servicios/puyehue_5.JPG',
    'Tina Calbuco': 'https://res.cloudinary.com/dtuncr1pi/servicios/calbuco3.jpg',
    'Cabaña Laurel': 'https://res.cloudinary.com/dtuncr1pi/servicios/laurel1.jpeg',
    'Desayuno': 'https://res.cloudinary.com/dtuncr1pi/servicios/desayuno.jpg',
    'Cabaña Arrayan': 'https://res.cloudinary.com/dtuncr1pi/servicios/arrayan4.jpg',
    'Cabaña Acantilado': 'https://res.cloudinary.com/dtuncr1pi/servicios/acantiladoalda.jpg',
    'Cabaña Torre': 'https://res.cloudinary.com/dtuncr1pi/servicios/Torre_1.jpeg',
}

def download_and_upload(url, public_id):
    """Descarga una imagen y la sube a Cloudinary"""
    try:
        # Si la URL ya es de Cloudinary, intentar descargar
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            # Subir a Cloudinary con el public_id correcto
            result = cloudinary.uploader.upload(
                response.content,
                public_id=public_id,
                folder='servicios',
                overwrite=True,
                resource_type='image'
            )
            return result['public_id']
        else:
            print(f"  ❌ No se pudo descargar: HTTP {response.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return None

# Primero, verificar qué hay en Cloudinary
print("\n🔍 VERIFICANDO CLOUDINARY:")
print("-" * 40)

try:
    result = cloudinary.api.resources(
        type='upload',
        prefix='servicios/',
        max_results=50
    )

    existing_images = [r['public_id'] for r in result['resources']]
    print(f"Imágenes existentes en Cloudinary: {len(existing_images)}")
    for img in existing_images[:5]:
        print(f"  - {img}")

except Exception as e:
    print(f"Error listando recursos: {e}")
    existing_images = []

# Procesar servicios
print("\n📦 PROCESANDO SERVICIOS:")
print("-" * 40)

servicios = Servicio.objects.all()
fixed = 0
failed = 0

for s in servicios:
    # Si el servicio está en la lista de imágenes conocidas
    if s.nombre in KNOWN_IMAGES:
        print(f"\n🔧 {s.nombre}:")

        # Obtener el nombre del archivo de la URL
        url = KNOWN_IMAGES[s.nombre]
        filename = url.split('/')[-1]
        public_id = f"servicios/{filename.split('.')[0]}"

        print(f"  URL original: {url[:60]}...")
        print(f"  Public ID: {public_id}")

        # Verificar si ya existe en Cloudinary
        if public_id in existing_images:
            print(f"  ✓ Ya existe en Cloudinary")
            # Actualizar el campo imagen con el formato correcto
            s.imagen.name = f"servicios/{filename}"
            s.save(update_fields=['imagen'])
            fixed += 1
        else:
            # Intentar descargar y subir
            print(f"  📤 Subiendo a Cloudinary...")
            result = download_and_upload(url, filename.split('.')[0])
            if result:
                print(f"  ✅ Subido exitosamente")
                s.imagen.name = f"servicios/{filename}"
                s.save(update_fields=['imagen'])
                fixed += 1
            else:
                failed += 1

# Para servicios sin imagen conocida, intentar arreglar el formato
print("\n🔧 ARREGLANDO FORMATOS:")
print("-" * 40)

for s in Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True):
    if s.imagen.name and not s.imagen.name.startswith('servicios/'):
        old_name = s.imagen.name
        # Si es solo un nombre de archivo, agregar el prefijo
        new_name = f"servicios/{old_name}"
        s.imagen.name = new_name
        s.save(update_fields=['imagen'])
        print(f"  {s.nombre}: {old_name} → {new_name}")
        fixed += 1

print("\n" + "=" * 60)
print("RESUMEN")
print("=" * 60)
print(f"✅ Arreglados: {fixed}")
print(f"❌ Fallidos: {failed}")

print("\n💡 SIGUIENTE PASO:")
print("Si las imágenes aún no se ven:")
print("1. Verificar en https://console.cloudinary.com que las imágenes estén ahí")
print("2. Limpiar caché del navegador (Ctrl+Shift+R)")
print("3. Verificar que las URLs generadas sean correctas")

# Verificación final
print("\n✨ VERIFICACIÓN:")
print("-" * 40)

test_service = Servicio.objects.filter(nombre__icontains='llaima').first()
if test_service and test_service.imagen:
    print(f"Servicio de prueba: {test_service.nombre}")
    print(f"  imagen.name: {test_service.imagen.name}")
    print(f"  imagen.url: {test_service.imagen.url}")

    # Verificar que la URL sea accesible
    if test_service.imagen.url.startswith('http'):
        try:
            response = requests.head(test_service.imagen.url, timeout=5)
            if response.status_code == 200:
                print(f"  ✅ Imagen accesible")
            else:
                print(f"  ❌ HTTP {response.status_code}")
        except:
            print(f"  ⚠️ No se pudo verificar")