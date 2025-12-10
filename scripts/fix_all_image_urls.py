#!/usr/bin/env python
"""
Script para arreglar TODAS las URLs de imágenes que no están funcionando.
Convierte los nombres de archivo simples a URLs completas de Cloudinary.
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

from ventas.models import Servicio, CategoriaServicio
from django.conf import settings

print("=" * 60)
print("FIX: REPARAR TODAS LAS URLS DE IMÁGENES")
print("=" * 60)

# Obtener el cloud name de Cloudinary
CLOUD_NAME = getattr(settings, 'CLOUDINARY_CLOUD_NAME', 'dtuncr1pi')

print(f"\nCloud Name: {CLOUD_NAME}")
print("-" * 40)

def needs_fixing(image_name):
    """Verifica si una imagen necesita ser arreglada"""
    if not image_name:
        return False

    # Si ya es una URL completa correcta, no necesita fix
    if image_name.startswith('http://') or image_name.startswith('https://'):
        return False

    # Si ya tiene el formato correcto de Cloudinary (carpeta/archivo), está bien
    if image_name.startswith('servicios/') and not image_name.startswith('http'):
        return False

    # Todo lo demás necesita fix
    return True

def fix_image_name(image_name, folder='servicios'):
    """Arregla el nombre de la imagen para que funcione con Cloudinary"""

    # Si no hay nombre, retornar vacío
    if not image_name:
        return ''

    # Si ya es una URL completa, extraer solo el nombre del archivo
    if image_name.startswith('http'):
        # Intentar extraer el public_id de una URL de Cloudinary
        if 'cloudinary.com' in image_name:
            parts = image_name.split('/')
            # Buscar la parte después del cloud name
            if CLOUD_NAME in image_name:
                idx = parts.index(CLOUD_NAME)
                if idx < len(parts) - 1:
                    # Tomar todo después del cloud name
                    return '/'.join(parts[idx+1:])
        # Si no se puede parsear, usar el último segmento
        return f"{folder}/{image_name.split('/')[-1]}"

    # Si ya tiene carpeta, dejarlo así
    if '/' in image_name:
        return image_name

    # Si es solo un nombre de archivo, agregar carpeta
    return f"{folder}/{image_name}"

# Procesar Servicios
print("\n📦 PROCESANDO SERVICIOS:")
print("-" * 40)

servicios = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
total_servicios = servicios.count()
fixed_servicios = 0

for s in servicios:
    old_name = s.imagen.name

    if needs_fixing(old_name):
        new_name = fix_image_name(old_name, 'servicios')

        if new_name != old_name:
            print(f"\n🔧 {s.nombre}:")
            print(f"   Antes: {old_name}")
            print(f"   Después: {new_name}")

            s.imagen.name = new_name
            s.save(update_fields=['imagen'])
            fixed_servicios += 1

print(f"\n✅ Servicios procesados: {total_servicios}")
print(f"   Corregidos: {fixed_servicios}")

# Procesar Categorías
print("\n📦 PROCESANDO CATEGORÍAS:")
print("-" * 40)

categorias = CategoriaServicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
total_categorias = categorias.count()
fixed_categorias = 0

for c in categorias:
    old_name = c.imagen.name

    if needs_fixing(old_name):
        new_name = fix_image_name(old_name, 'categorias')

        if new_name != old_name:
            print(f"\n🔧 {c.nombre}:")
            print(f"   Antes: {old_name}")
            print(f"   Después: {new_name}")

            c.imagen.name = new_name
            c.save(update_fields=['imagen'])
            fixed_categorias += 1

print(f"\n✅ Categorías procesadas: {total_categorias}")
print(f"   Corregidas: {fixed_categorias}")

# Verificación final
print("\n✨ VERIFICACIÓN FINAL:")
print("-" * 40)

# Verificar algunos servicios específicos
test_services = [
    'Tina Hidromasaje Llaima',
    'Tina Tronador',
    'Masaje Relajación o Descontracturante'
]

for service_name in test_services:
    try:
        s = Servicio.objects.filter(nombre__icontains=service_name.split()[-1]).first()
        if s and s.imagen:
            print(f"\n{s.nombre}:")
            print(f"  imagen.name: {s.imagen.name}")
            print(f"  URL generada: {s.imagen.url}")

            # Verificar formato
            if s.imagen.url.startswith(f'https://res.cloudinary.com/{CLOUD_NAME}/'):
                print(f"  ✅ URL correcta")
            else:
                print(f"  ⚠️ URL puede tener problemas")
    except Exception as e:
        print(f"Error verificando {service_name}: {e}")

print("\n" + "=" * 60)
print("PROCESO COMPLETADO")
print("=" * 60)

print("\n💡 NOTA IMPORTANTE:")
print("Las imágenes que no tienen extensión (como 'tina_llaima_avyg3p')")
print("son public_ids de Cloudinary y funcionan sin extensión.")
print("\nSi aún no se ven las imágenes, puede ser necesario:")
print("1. Limpiar caché del navegador")
print("2. Verificar que las imágenes existen en Cloudinary Dashboard")
print("3. Re-subir las imágenes que fallan")