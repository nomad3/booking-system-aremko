#!/usr/bin/env python
"""
Script para debuggear por qué las imágenes no se muestran en el template.
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
import requests

print("=" * 60)
print("DEBUG: IMÁGENES EN TEMPLATES")
print("=" * 60)

# Buscar el servicio Tina Llaima
servicios_tina = Servicio.objects.filter(nombre__icontains='llaima')

for servicio in servicios_tina:
    print(f"\n📦 Servicio: {servicio.nombre} (ID: {servicio.id})")
    print("-" * 40)

    if servicio.imagen:
        print(f"✓ Campo imagen existe")
        print(f"  imagen.name: {servicio.imagen.name}")

        # Verificar diferentes formas de obtener la URL
        try:
            url = servicio.imagen.url
            print(f"  imagen.url: {url}")

            # Verificar si la URL es accesible
            if url.startswith('http'):
                response = requests.head(url, timeout=5)
                print(f"  HTTP Status: {response.status_code}")

                if response.status_code == 200:
                    print(f"  ✅ Imagen accesible en: {url}")
                else:
                    print(f"  ❌ Imagen no accesible (HTTP {response.status_code})")

        except Exception as e:
            print(f"  ❌ Error obteniendo URL: {e}")
    else:
        print("❌ No tiene imagen asignada")

# Verificar todos los servicios con problemas potenciales
print("\n🔍 VERIFICANDO TODOS LOS SERVICIOS CON IMÁGENES:")
print("-" * 40)

servicios = Servicio.objects.exclude(imagen='').exclude(imagen__isnull=True)
problemas = []

for s in servicios:
    try:
        # Verificar si el name empieza con http (problema anterior)
        if s.imagen.name.startswith('http'):
            problemas.append(f"{s.nombre}: imagen.name empieza con http")

        # Verificar si la URL se duplica
        url = s.imagen.url
        if url.count('cloudinary.com') > 1:
            problemas.append(f"{s.nombre}: URL duplicada")

        # Verificar si falta la extensión
        if not any(ext in s.imagen.name for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            # Cloudinary puede no tener extensión, verificar si es un public_id válido
            if '/' in s.imagen.name and len(s.imagen.name.split('/')[-1]) > 5:
                pass  # Probablemente es un public_id de Cloudinary
            else:
                problemas.append(f"{s.nombre}: Posible falta de extensión")

    except Exception as e:
        problemas.append(f"{s.nombre}: Error - {e}")

if problemas:
    print("\n⚠️ PROBLEMAS ENCONTRADOS:")
    for p in problemas:
        print(f"  • {p}")
else:
    print("✅ No se encontraron problemas obvios")

# Verificar el template
print("\n📄 VERIFICACIÓN DE TEMPLATE:")
print("-" * 40)

template_paths = [
    'ventas/templates/ventas/servicio_list.html',
    'ventas/templates/ventas/servicio_detail.html',
    'templates/servicio_list.html',
]

print("Posibles ubicaciones de templates:")
for path in template_paths:
    full_path = BASE_DIR / path
    if full_path.exists():
        print(f"  ✅ {path} existe")

        # Buscar cómo se muestra la imagen
        with open(full_path, 'r') as f:
            content = f.read()
            if 'servicio.imagen' in content:
                print(f"     Usa servicio.imagen")

                # Buscar el contexto exacto
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'servicio.imagen' in line:
                        print(f"     Línea {i+1}: {line.strip()[:80]}...")
    else:
        print(f"  ❌ {path} no existe")

print("\n💡 RECOMENDACIONES:")
print("-" * 40)
print("En el template, la imagen debería mostrarse así:")
print("  {% if servicio.imagen %}")
print("    <img src=\"{{ servicio.imagen.url }}\" alt=\"{{ servicio.nombre }}\">")
print("  {% endif %}")
print("\nO con un default:")
print("  <img src=\"{% if servicio.imagen %}{{ servicio.imagen.url }}{% else %}/static/img/default.jpg{% endif %}\" alt=\"{{ servicio.nombre }}\">")

print("\n" + "=" * 60)