#!/usr/bin/env python3
"""
Script de diagnóstico para verificar que el admin funcione correctamente
Ejecutar desde Render: python scripts/diagnose_error.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import CategoriaServicio, SEOContent

print("\n" + "=" * 70)
print("DIAGNÓSTICO DE CATEGORÍAS Y SEO")
print("=" * 70)

# Test 1: Verificar categorías
print("\n📋 TEST 1: Categorías de Servicio")
print("-" * 70)
try:
    categorias = CategoriaServicio.objects.all()
    print(f"✅ Total categorías: {categorias.count()}")

    for cat in categorias:
        print(f"\nID {cat.id}: {cat.nombre}")
        print(f"   Horarios: {cat.horarios or 'No definidos'}")
        print(f"   Imagen: {cat.imagen or 'Sin imagen'}")
        if cat.imagen:
            try:
                print(f"   URL imagen: {cat.imagen.url}")
            except Exception as e:
                print(f"   ⚠️ Error obteniendo URL: {e}")
except Exception as e:
    print(f"❌ Error obteniendo categorías: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Verificar contenido SEO
print("\n\n📋 TEST 2: Contenido SEO")
print("-" * 70)
try:
    seo_contents = SEOContent.objects.all()
    print(f"✅ Total contenidos SEO: {seo_contents.count()}")

    for seo in seo_contents:
        print(f"\nSEO para: {seo.categoria.nombre if seo.categoria else 'Sin categoría'}")
        print(f"   Meta title: {seo.meta_title[:50]}...")
        if seo.categoria and seo.categoria.imagen:
            try:
                print(f"   Imagen categoría: {seo.categoria.imagen.url}")
            except Exception as e:
                print(f"   ⚠️ Error con imagen: {e}")
except Exception as e:
    print(f"❌ Error obteniendo SEO content: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Simular métodos del admin
print("\n\n📋 TEST 3: Simular métodos del admin")
print("-" * 70)
try:
    from ventas.admin import CategoriaServicioAdmin, SEOContentAdmin
    from django.contrib.admin.sites import AdminSite

    site = AdminSite()
    cat_admin = CategoriaServicioAdmin(CategoriaServicio, site)
    seo_admin = SEOContentAdmin(SEOContent, site)

    # Test con una categoría
    cat = CategoriaServicio.objects.first()
    if cat:
        print(f"\nTesteando admin con categoría: {cat.nombre}")
        try:
            preview = cat_admin.imagen_preview(cat)
            print(f"   ✅ imagen_preview: OK")
        except Exception as e:
            print(f"   ❌ imagen_preview: {e}")

        try:
            preview_large = cat_admin.imagen_preview_large(cat)
            print(f"   ✅ imagen_preview_large: OK")
        except Exception as e:
            print(f"   ❌ imagen_preview_large: {e}")

    # Test con contenido SEO
    seo = SEOContent.objects.first()
    if seo:
        print(f"\nTesteando admin con SEO: {seo.categoria.nombre if seo.categoria else 'N/A'}")
        try:
            preview = seo_admin.imagen_categoria_preview(seo)
            print(f"   ✅ imagen_categoria_preview: OK")
        except Exception as e:
            print(f"   ❌ imagen_categoria_preview: {e}")

        try:
            info = seo_admin.categoria_imagen_info(seo)
            print(f"   ✅ categoria_imagen_info: OK")
        except Exception as e:
            print(f"   ❌ categoria_imagen_info: {e}")

except Exception as e:
    print(f"❌ Error al testear admin: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("DIAGNÓSTICO COMPLETADO")
print("=" * 70 + "\n")
