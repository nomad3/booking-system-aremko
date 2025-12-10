#!/usr/bin/env python
"""
Script para arreglar las URLs duplicadas de Cloudinary en los campos de imagen.
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

from ventas.models import Servicio, CategoriaServicio, GiftCardExperiencia

print("=" * 60)
print("FIX: URLS DUPLICADAS DE CLOUDINARY")
print("=" * 60)

def fix_image_urls(model_class, image_field='imagen'):
    """Arregla las URLs duplicadas en un modelo"""

    model_name = model_class.__name__
    print(f"\n📦 Procesando {model_name}:")
    print("-" * 40)

    # Obtener objetos con imágenes
    objects = model_class.objects.exclude(**{f"{image_field}__isnull": True}).exclude(**{image_field: ''})

    fixed = 0
    skipped = 0

    for obj in objects:
        image = getattr(obj, image_field)

        if image and image.name:
            # Verificar si el nombre contiene una URL completa
            if image.name.startswith('http'):
                print(f"\n🔧 {obj}: Necesita corrección")
                print(f"   Antes: {image.name}")

                # Extraer solo el path relativo
                # Formato esperado: servicios/nombre_archivo
                if 'cloudinary.com' in image.name and 'dtuncr1pi/' in image.name:
                    # Extraer la parte después del cloud name
                    parts = image.name.split('dtuncr1pi/')
                    if len(parts) > 1:
                        new_name = parts[1]
                        image.name = new_name
                        obj.save(update_fields=[image_field])
                        print(f"   Después: {new_name}")
                        print(f"   ✅ Corregido")
                        fixed += 1
                    else:
                        print(f"   ⚠️ No se pudo extraer el path")
                        skipped += 1
                else:
                    print(f"   ⚠️ Formato de URL no reconocido")
                    skipped += 1
            else:
                # Ya está en formato correcto
                skipped += 1

    print(f"\nResumen {model_name}:")
    print(f"  ✅ Corregidos: {fixed}")
    print(f"  ⏭️ Sin cambios: {skipped}")

    return fixed, skipped

# Verificar antes de arreglar
print("\n🔍 DIAGNÓSTICO INICIAL:")
print("-" * 40)

total_problemas = 0

# Verificar Servicios
servicios = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
for s in servicios:
    if s.imagen.name.startswith('http'):
        print(f"• {s.nombre}: {s.imagen.name[:50]}...")
        total_problemas += 1

# Verificar CategoriaServicio
categorias = CategoriaServicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
for c in categorias:
    if c.imagen.name.startswith('http'):
        print(f"• {c.nombre}: {c.imagen.name[:50]}...")
        total_problemas += 1

if total_problemas == 0:
    print("✅ No se encontraron URLs duplicadas")
else:
    print(f"\n⚠️ Total de imágenes con problema: {total_problemas}")

    # Preguntar confirmación
    print("\n" + "=" * 60)
    response = input("¿Deseas corregir las URLs duplicadas? (s/n): ")

    if response.lower() == 's':
        print("\n🔧 APLICANDO CORRECCIONES:")
        print("=" * 60)

        total_fixed = 0

        # Arreglar cada modelo
        for model_class in [Servicio, CategoriaServicio]:
            try:
                fixed, skipped = fix_image_urls(model_class)
                total_fixed += fixed
            except Exception as e:
                print(f"❌ Error procesando {model_class.__name__}: {e}")

        # Verificar después de arreglar
        print("\n✨ VERIFICACIÓN FINAL:")
        print("-" * 40)

        # Verificar un servicio específico
        try:
            s14 = Servicio.objects.get(pk=14)
            print(f"Servicio 14 - {s14.nombre}:")
            print(f"  imagen.name: {s14.imagen.name}")
            print(f"  imagen.url: {s14.imagen.url}")

            if not s14.imagen.url.startswith('https://res.cloudinary.com/dtuncr1pi/https:'):
                print(f"  ✅ URL correcta")
            else:
                print(f"  ❌ Todavía tiene problema")
        except:
            pass

        print("\n" + "=" * 60)
        print(f"✅ PROCESO COMPLETADO")
        print(f"   Total corregidas: {total_fixed}")
        print("=" * 60)
    else:
        print("Proceso cancelado")

print("\n")