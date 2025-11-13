#!/usr/bin/env python
"""
Script de diagnóstico para error en /ventas/categoria/3/
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import CategoriaServicio, Servicio
from django.template.loader import get_template

print("=" * 80)
print("🔍 DIAGNÓSTICO: Error en /ventas/categoria/3/")
print("=" * 80)

# 1. Verificar categoría 3
print("\n1️⃣ VERIFICANDO CATEGORÍA 3:")
try:
    cat = CategoriaServicio.objects.get(id=3)
    print(f"✅ Categoría encontrada: {cat.nombre}")
    print(f"   - ID: {cat.id}")
    if hasattr(cat, 'imagen'):
        print(f"   - Imagen: {cat.imagen}")
        if cat.imagen:
            try:
                url = cat.imagen.url
                print(f"   - URL imagen: {url}")
            except Exception as e:
                print(f"   ⚠️  Error obteniendo URL imagen: {e}")
    else:
        print(f"   - No tiene campo 'imagen'")
except CategoriaServicio.DoesNotExist:
    print("❌ Categoría 3 NO existe en la base de datos")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. Verificar servicios de esa categoría
print("\n2️⃣ VERIFICANDO SERVICIOS:")
try:
    servicios = Servicio.objects.filter(categoria=cat, activo=True, publicado_web=True)
    print(f"✅ Total servicios activos y publicados: {servicios.count()}")

    for s in servicios:
        print(f"\n   📦 {s.nombre}")
        print(f"      - ID: {s.id}")
        print(f"      - Activo: {s.activo}")
        print(f"      - Publicado web: {s.publicado_web}")
        if hasattr(s, 'imagen'):
            print(f"      - Imagen: {s.imagen}")
            if s.imagen:
                try:
                    url = s.imagen.url
                    print(f"      - URL imagen: {url}")
                except Exception as e:
                    print(f"      ⚠️  Error obteniendo URL: {e}")
        if hasattr(s, 'precio'):
            print(f"      - Precio: ${s.precio}")

except Exception as e:
    print(f"❌ Error obteniendo servicios: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 3. Verificar template
print("\n3️⃣ VERIFICANDO TEMPLATE:")
try:
    template = get_template('ventas/category_detail.html')
    print(f"✅ Template encontrado: category_detail.html")
except Exception as e:
    print(f"❌ Error cargando template: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 4. Verificar filtros personalizados
print("\n4️⃣ VERIFICANDO FILTROS PERSONALIZADOS:")
try:
    from django.template import Template, Context
    test_template = Template("{% load ventas_extras %}")
    test_template.render(Context({}))
    print(f"✅ Filtros ventas_extras cargados correctamente")
except Exception as e:
    print(f"❌ Error cargando filtros: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

# 5. Simular la vista
print("\n5️⃣ SIMULANDO LA VISTA:")
try:
    from django.test import RequestFactory
    from ventas.views.public_views import categoria_detail_view

    factory = RequestFactory()
    request = factory.get('/ventas/categoria/3/')
    request.session = {}

    print("   Ejecutando categoria_detail_view(request, categoria_id=3)...")
    response = categoria_detail_view(request, categoria_id=3)
    print(f"✅ Vista ejecutada exitosamente")
    print(f"   - Status code: {response.status_code}")

except Exception as e:
    print(f"❌ ERROR EN LA VISTA: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    print("\n⚠️  ESTE ES EL ERROR QUE CAUSA EL 500 ⚠️")

print("\n" + "=" * 80)
print("🏁 FIN DEL DIAGNÓSTICO")
print("=" * 80)
