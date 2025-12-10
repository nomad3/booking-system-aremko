#!/usr/bin/env python
"""
Script simple para limpiar URLs y verificar imágenes.
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

print("=" * 60)
print("FIX SIMPLE: LIMPIEZA DE URLs DE IMÁGENES")
print("=" * 60)

# Cloud name de Cloudinary
CLOUD_NAME = 'dtuncr1pi'

def clean_image_name(name):
    """Limpia un nombre de imagen que contiene URL completa"""
    if not name:
        return name

    # Si no empieza con http, ya está bien
    if not name.startswith('http'):
        return name

    # Extraer el path después del cloud name
    if f'/{CLOUD_NAME}/' in name:
        parts = name.split(f'/{CLOUD_NAME}/')
        if len(parts) > 1:
            # Limpiar posibles dobles barras o http extras
            clean = parts[1].replace('//', '/').replace('http:', '').replace('https:', '')
            return clean.strip('/')

    # Si contiene 'servicios/', extraer desde ahí
    if 'servicios/' in name:
        idx = name.find('servicios/')
        return name[idx:]

    # Si no se puede parsear, retornar como está
    return name

# Encontrar todos los servicios con imágenes problemáticas
print("\n🔍 BUSCANDO IMÁGENES CON PROBLEMAS...")
print("-" * 40)

servicios = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
problemas = []

for s in servicios:
    if s.imagen.name and s.imagen.name.startswith('http'):
        problemas.append(s)

print(f"Servicios con URLs problemáticas: {len(problemas)}")

if problemas:
    print("\n🔧 LIMPIANDO URLs...")
    print("-" * 40)

    for s in problemas:
        old_name = s.imagen.name
        new_name = clean_image_name(old_name)

        if new_name != old_name:
            print(f"\n• {s.nombre[:40]}...")
            print(f"  Antes: {old_name[:60]}...")
            print(f"  Después: {new_name}")

            s.imagen.name = new_name
            s.save(update_fields=['imagen'])
            print(f"  ✅ Corregido")

    print(f"\n✅ Limpiados: {len(problemas)} servicios")
else:
    print("✅ No se encontraron URLs problemáticas")

# Verificación de algunos servicios clave
print("\n" + "=" * 60)
print("VERIFICACIÓN DE SERVICIOS CLAVE")
print("=" * 60)

servicios_prueba = [
    'llaima',
    'tronador',
    'masaje',
    'torre',
    'villarrica'
]

for keyword in servicios_prueba:
    s = Servicio.objects.filter(nombre__icontains=keyword).first()
    if s:
        print(f"\n📦 {s.nombre}:")
        if s.imagen:
            print(f"  ✓ Tiene imagen")
            print(f"  Name: {s.imagen.name}")
            try:
                url = s.imagen.url
                print(f"  URL: {url}")

                # Verificar formato
                if url.startswith(f'https://res.cloudinary.com/{CLOUD_NAME}/'):
                    if url.count('http') == 1 and url.count('//') <= 2:
                        print(f"  ✅ URL parece correcta")
                    else:
                        print(f"  ⚠️ URL puede tener problemas")
                else:
                    print(f"  ❌ URL no tiene formato esperado")
            except Exception as e:
                print(f"  ❌ Error: {e}")
        else:
            print(f"  ❌ Sin imagen")

print("\n" + "=" * 60)
print("COMPLETADO")
print("=" * 60)
print("\n💡 SIGUIENTE PASO:")
print("Si las URLs ahora se ven correctas pero las imágenes aún no cargan,")
print("el problema es que las imágenes no existen en Cloudinary.")
print("Necesitarás subirlas nuevamente desde Django Admin.")
