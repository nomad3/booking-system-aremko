#!/usr/bin/env python
"""
Script para resetear y arreglar completamente el problema de imágenes.
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
from django.core.files.base import ContentFile
from PIL import Image
import io

print("=" * 60)
print("RESET Y FIX DE IMÁGENES")
print("=" * 60)

# Mapeo de servicios a sus imágenes correctas (basado en lo que funcionaba antes)
IMAGE_MAP = {
    'Decoración cumpleaños C2 Varon': 'cumpleaños_C2_version_4.jpeg',
    'Decoración cumpleaños C1 Varon': 'cumpleaños3alda.jpeg',
    'Cabaña Tepa': 'Tepa_3.jpg',
    'Masaje Relajación o Descontracturante': 'masajepara2.jpg',
    'Tina Hidromasaje Villarrica': 'tina_villarrica.jpeg',
    'Tina Hidromasaje Puntiagudo': 'Captura_de_pantalla_2025-09-06_a_las_7.16.04p.m..png',
    'Tina Hidromasaje Niño': 'damiancito2.jpg',
    'Decoración Cumpleaños C1 Dama': 'cumpleaños3alda_eHYNW5f.jpeg',
    'Decoración cumpleaños C2 Dama': 'cumpleaños_C2_version_4.jpeg',
    'Tina Hidromasaje Llaima': 'llaima_foto.jpeg',
    'Tina Tronador': 'tronador1.jpeg',
    'Tina Hornopiren': 'hornopirenmama.jpg',
    'Tina Osorno': 'amigasosorno.jpg',
    'Tina de Agua Fria Yates': 'Generated_Image_August_30_2025_-_4_15PM.jpeg',
    'Tina Hidromasaje Puyehue': 'puyehue_5.JPG',
    'Tina Calbuco': 'calbuco3.jpg',
    'Tina Normal Niño 10.000': 'nino10mil.jpg',
    'Cabaña Laurel': 'laurel1.jpeg',
    'Desayuno': 'desayuno.jpg',
    'Cabaña Arrayan': 'arrayan4.jpg',
    'Cabaña Acantilado': 'acantiladoalda.jpg',
    'Cabaña Torre': 'Torre_1.jpeg'
}

def create_placeholder_image(text, width=800, height=600):
    """Crea una imagen placeholder con texto"""
    # Crear imagen con fondo de color
    img = Image.new('RGB', (width, height), color=(100, 150, 200))

    # Convertir a bytes
    img_buffer = io.BytesIO()
    img.save(img_buffer, format='PNG')
    img_buffer.seek(0)

    return img_buffer.getvalue()

print("\n🔧 PASO 1: LIMPIAR URLS CORRUPTAS")
print("-" * 40)

servicios = Servicio.objects.all()
cleaned = 0

for s in servicios:
    if s.imagen and s.imagen.name:
        # Si el nombre contiene "http" o está mal formado, limpiarlo
        if 'http' in s.imagen.name or s.imagen.name.count('/') > 1:
            print(f"Limpiando {s.nombre}: {s.imagen.name[:50]}...")

            # Obtener el nombre del archivo esperado
            if s.nombre in IMAGE_MAP:
                clean_name = f"servicios/{IMAGE_MAP[s.nombre]}"
            else:
                # Usar el último segmento como nombre
                parts = s.imagen.name.split('/')
                filename = parts[-1]
                if 'http' in filename:
                    filename = f"servicio_{s.id}.jpg"
                clean_name = f"servicios/{filename}"

            s.imagen.name = clean_name
            s.save(update_fields=['imagen'])
            cleaned += 1

print(f"✅ URLs limpiadas: {cleaned}")

print("\n🔧 PASO 2: CREAR IMÁGENES PLACEHOLDER")
print("-" * 40)
print("Como las imágenes originales no están disponibles,")
print("vamos a crear placeholders temporales para que el sitio funcione.")

response = input("\n¿Crear imágenes placeholder para servicios sin imagen válida? (s/n): ")

if response.lower() == 's':
    from django.core.files.storage import default_storage
    import cloudinary.uploader

    created = 0

    for s in servicios:
        if s.nombre in IMAGE_MAP:
            print(f"\n📸 {s.nombre}:")

            # Crear imagen placeholder
            img_data = create_placeholder_image(s.nombre)

            # Nombre del archivo
            filename = IMAGE_MAP[s.nombre]

            try:
                # Subir a Cloudinary
                result = cloudinary.uploader.upload(
                    img_data,
                    public_id=f"servicios/{filename.split('.')[0]}",
                    folder='',
                    overwrite=True,
                    resource_type='image'
                )

                # Actualizar el servicio
                s.imagen.name = f"servicios/{filename}"
                s.save(update_fields=['imagen'])

                print(f"  ✅ Placeholder creado: {result['secure_url'][:60]}...")
                created += 1

            except Exception as e:
                print(f"  ❌ Error: {e}")

    print(f"\n✅ Placeholders creados: {created}")

else:
    print("Saltando creación de placeholders...")

print("\n🔧 PASO 3: VERIFICACIÓN FINAL")
print("-" * 40)

# Verificar algunos servicios
test_services = ['Tina Hidromasaje Llaima', 'Cabaña Torre', 'Masaje Relajación o Descontracturante']

for service_name in test_services:
    s = Servicio.objects.filter(nombre__icontains=service_name.split()[-1]).first()
    if s:
        print(f"\n{s.nombre}:")
        if s.imagen:
            print(f"  imagen.name: {s.imagen.name}")
            print(f"  imagen.url: {s.imagen.url}")

            # Verificar si la URL es válida
            if not s.imagen.url.count('http') > 1 and not s.imagen.url.count('//') > 2:
                print(f"  ✅ URL parece correcta")
            else:
                print(f"  ⚠️ URL todavía tiene problemas")

print("\n" + "=" * 60)
print("PROCESO COMPLETADO")
print("=" * 60)

print("\n💡 SIGUIENTE PASO:")
print("1. Si creaste placeholders, las imágenes deberían funcionar")
print("2. Para restaurar las imágenes originales:")
print("   - Sube las imágenes reales desde Django Admin")
print("   - O proporciona un backup de las imágenes originales")
print("\n⚠️ IMPORTANTE:")
print("Las imágenes placeholder son temporales.")
print("Debes subir las imágenes reales lo antes posible.")