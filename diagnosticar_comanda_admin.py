#!/usr/bin/env python
"""
Script de diagnóstico para el problema del formulario de Comanda en blanco.
Ejecutar en Render Shell: python diagnosticar_comanda_admin.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.contrib.admin.sites import site
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from ventas.models import Comanda, VentaReserva
from ventas.admin import ComandaAdmin

User = get_user_model()

print("=" * 80)
print("🔍 DIAGNÓSTICO: Formulario de Comanda")
print("=" * 80)

# TEST 1: Verificar que ComandaAdmin está registrado
print("\n📋 TEST 1: ComandaAdmin registrado en admin")
print("-" * 80)
try:
    admin_class = site._registry.get(Comanda)
    if admin_class:
        print(f"✅ ComandaAdmin registrado: {admin_class}")
        print(f"   Clase: {admin_class.__class__.__name__}")
    else:
        print("❌ ComandaAdmin NO está registrado")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)

# TEST 2: Verificar que existe una VentaReserva
print("\n📋 TEST 2: Verificar VentaReserva de prueba")
print("-" * 80)
try:
    venta_reserva = VentaReserva.objects.filter(pk=4892).first()
    if venta_reserva:
        print(f"✅ VentaReserva #{venta_reserva.id} existe")
        print(f"   Cliente: {venta_reserva.cliente.nombre if venta_reserva.cliente else 'Sin cliente'}")
    else:
        print("⚠️  VentaReserva #4892 no existe, usando otra...")
        venta_reserva = VentaReserva.objects.first()
        if venta_reserva:
            print(f"✅ Usando VentaReserva #{venta_reserva.id}")
        else:
            print("❌ No hay VentaReservas en la BD")
            sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 3: Crear request simulado
print("\n📋 TEST 3: Crear request simulado")
print("-" * 80)
try:
    factory = RequestFactory()
    request = factory.get(f'/admin/ventas/comanda/add/?venta_reserva={venta_reserva.id}&_popup=1')

    # Agregar usuario
    user = User.objects.filter(is_superuser=True).first()
    if not user:
        user = User.objects.filter(is_staff=True).first()

    if user:
        request.user = user
        print(f"✅ Request creado con usuario: {user.username}")
    else:
        print("❌ No hay usuarios staff/superuser en la BD")
        sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 4: Instanciar ComandaAdmin
print("\n📋 TEST 4: Instanciar ComandaAdmin")
print("-" * 80)
try:
    comanda_admin = ComandaAdmin(Comanda, site)
    print(f"✅ ComandaAdmin instanciado correctamente")
    print(f"   Fieldsets: {len(comanda_admin.fieldsets)} secciones")
    print(f"   Inlines: {len(comanda_admin.inlines)} inlines")
except Exception as e:
    print(f"❌ Error al instanciar ComandaAdmin: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 5: Obtener formulario
print("\n📋 TEST 5: Obtener formulario (get_form)")
print("-" * 80)
try:
    form_class = comanda_admin.get_form(request, obj=None)
    print(f"✅ Formulario obtenido: {form_class}")
    print(f"   Campos: {list(form_class.base_fields.keys())}")

    # Verificar campo venta_reserva
    if 'venta_reserva' in form_class.base_fields:
        vr_field = form_class.base_fields['venta_reserva']
        print(f"\n   Campo venta_reserva:")
        print(f"   - Tipo: {type(vr_field).__name__}")
        print(f"   - Widget: {type(vr_field.widget).__name__}")
        print(f"   - Initial: {vr_field.initial}")
except Exception as e:
    print(f"❌ Error al obtener formulario: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 6: Instanciar formulario con initial
print("\n📋 TEST 6: Instanciar formulario con venta_reserva inicial")
print("-" * 80)
try:
    form = form_class(initial={'venta_reserva': venta_reserva.id})
    print(f"✅ Formulario instanciado")
    print(f"   Is valid (sin datos): {form.is_valid()}")

    if not form.is_valid():
        print(f"   Errores esperados (formulario vacío): {dict(form.errors)}")
except Exception as e:
    print(f"❌ Error al instanciar formulario: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# TEST 7: Verificar template
print("\n📋 TEST 7: Verificar template de Django Admin")
print("-" * 80)
try:
    from django.template.loader import get_template

    # Template por defecto de Django admin
    template = get_template('admin/change_form.html')
    print(f"✅ Template encontrado: admin/change_form.html")
    print(f"   Origen: {template.origin.name if hasattr(template, 'origin') else 'N/A'}")
except Exception as e:
    print(f"❌ Error al cargar template: {e}")
    import traceback
    traceback.print_exc()

# TEST 8: Simular vista add completa
print("\n📋 TEST 8: Simular vista add completa")
print("-" * 80)
try:
    from django.contrib import admin
    from django.urls import reverse

    # Obtener URL
    url = reverse('admin:ventas_comanda_add')
    print(f"✅ URL de add: {url}")

    # Simular changelist_view
    print(f"\n   Intentando renderizar vista add...")
    response = comanda_admin.add_view(request)

    print(f"✅ Vista add ejecutada")
    print(f"   Status code: {response.status_code}")
    print(f"   Content-Type: {response.get('Content-Type', 'N/A')}")

    if response.status_code == 200:
        content = response.content.decode('utf-8')
        print(f"   Longitud del HTML: {len(content)} caracteres")

        # Buscar elementos clave en el HTML
        if '<form' in content:
            print(f"   ✅ Contiene tag <form>")
        else:
            print(f"   ❌ NO contiene tag <form>")

        if 'venta_reserva' in content:
            print(f"   ✅ Contiene campo venta_reserva")
        else:
            print(f"   ❌ NO contiene campo venta_reserva")

        if 'csrfmiddlewaretoken' in content:
            print(f"   ✅ Contiene CSRF token")
        else:
            print(f"   ❌ NO contiene CSRF token")

        # Guardar HTML para inspección
        output_file = '/tmp/comanda_add_form.html'
        with open(output_file, 'w') as f:
            f.write(content)
        print(f"\n   💾 HTML guardado en: {output_file}")
        print(f"   Puedes ver con: cat {output_file} | head -100")

    elif response.status_code == 302:
        print(f"   ⚠️  Redirección a: {response.get('Location', 'N/A')}")
    else:
        print(f"   ❌ Status code inesperado: {response.status_code}")

except Exception as e:
    print(f"❌ Error al ejecutar vista add: {e}")
    import traceback
    traceback.print_exc()

# TEST 9: Verificar get_queryset optimizado
print("\n📋 TEST 9: Verificar optimización de queries")
print("-" * 80)
try:
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as queries:
        qs = comanda_admin.get_queryset(request)
        list(qs[:5])  # Evaluar queryset

    print(f"✅ get_queryset ejecutado")
    print(f"   Total queries: {len(queries)}")

    if len(queries) <= 10:
        print(f"   ✅ Queries optimizadas (<= 10)")
    else:
        print(f"   ⚠️  Muchas queries, revisar optimización")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

# RESUMEN
print("\n" + "=" * 80)
print("📊 RESUMEN DEL DIAGNÓSTICO")
print("=" * 80)
print("""
Si todos los tests pasaron ✅, el problema puede ser:

1. **Template bloqueado por CSP** (Content Security Policy)
   - Verificar en consola del navegador (F12)

2. **JavaScript bloqueado**
   - Verificar en Network tab del navegador

3. **Timeout del navegador**
   - El servidor responde pero el navegador cancela

4. **Problema con staticfiles**
   - CSS/JS del admin no se cargan

Próximos pasos:
- Revisar /tmp/comanda_add_form.html
- Verificar logs del navegador (F12 → Console)
- Verificar logs de Render durante la carga del popup
""")

print("\n✅ Diagnóstico completado")
