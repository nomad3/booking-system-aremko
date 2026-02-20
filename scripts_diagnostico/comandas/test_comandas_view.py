#!/usr/bin/env python
"""
Script para probar la vista de comandas y detectar errores
Ejecutar con: python manage.py shell < test_comandas_view.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from control_gestion.views_comandas import lista_comandas

print("\n" + "=" * 80)
print("TEST DE VISTA DE COMANDAS")
print("=" * 80)
print()

try:
    # Crear request simulado
    factory = RequestFactory()
    request = factory.get('/control_gestion/comandas/')

    # Simular usuario autenticado
    request.user = User.objects.filter(is_superuser=True).first()
    if not request.user:
        request.user = User.objects.first()

    print(f"Usuario simulado: {request.user}")

    # Intentar ejecutar la vista
    print("\nEjecutando vista lista_comandas...")

    try:
        response = lista_comandas(request)
        print(f"✓ Vista ejecutada exitosamente")
        print(f"  Status code: {getattr(response, 'status_code', 'N/A')}")

    except Exception as e:
        print(f"✗ ERROR en la vista: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()

        # Verificar imports específicos
        print("\nVerificando imports...")
        try:
            from ventas.models import Comanda
            print("✓ Comanda importado correctamente")
        except Exception as e:
            print(f"✗ Error importando Comanda: {e}")

        try:
            from control_gestion.views_comandas import lista_comandas
            print("✓ lista_comandas importado correctamente")
        except Exception as e:
            print(f"✗ Error importando lista_comandas: {e}")

except Exception as e:
    print(f"✗ Error general: {e}")
    import traceback
    traceback.print_exc()

# Verificar URLs
print("\n\nVERIFICANDO CONFIGURACIÓN DE URLs")
print("-" * 40)

try:
    from django.urls import reverse
    url = reverse('control_gestion:lista_comandas')
    print(f"✓ URL generada correctamente: {url}")
except Exception as e:
    print(f"✗ Error generando URL: {e}")

# Verificar template
print("\n\nVERIFICANDO TEMPLATES")
print("-" * 40)

import os
template_path = 'control_gestion/templates/control_gestion/comandas/lista.html'
full_path = os.path.join('/app', template_path)
print(f"Buscando template en: {full_path}")

if os.path.exists(full_path):
    print("✓ Template existe")
else:
    print("✗ Template NO encontrado")

    # Buscar en otras ubicaciones
    possible_paths = [
        '/app/control_gestion/templates/control_gestion/comandas/lista.html',
        '/app/templates/control_gestion/comandas/lista.html',
    ]

    for path in possible_paths:
        if os.path.exists(path):
            print(f"  → Encontrado en: {path}")

print("\n" + "=" * 80)
print("FIN DEL TEST")
print("=" * 80)