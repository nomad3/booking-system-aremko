# Script simplificado para capturar el error específico del popup
import os
import sys
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

# Habilitar logging detallado
import logging
logging.basicConfig(level=logging.DEBUG)

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from ventas.admin import ComandaAdmin
from ventas.models import Comanda
from django.http import QueryDict
import traceback

print("=== DEBUG ERROR POPUP COMANDA ===\n")

try:
    # Configurar admin
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Simular request POST desde popup
    post_data = {
        'venta_reserva': '4971',
        'mesa_numero': '1',
        'descripcion': 'Test desde popup',
        'estado': 'pendiente',
        'usuario_solicita': '1',  # Admin user
        'usuario_procesa': '1',   # Admin user
        # Campos de fecha y hora
        'fecha_solicitud_0': '2024-02-16',
        'fecha_solicitud_1': '10:00:00',
        'hora_solicitud': '10:00:00',
        # Popup flag
        '_popup': '1',
        '_save': 'Guardar',
        # Formset vacío
        'detalles-TOTAL_FORMS': '0',
        'detalles-INITIAL_FORMS': '0',
        'detalles-MIN_NUM_FORMS': '0',
        'detalles-MAX_NUM_FORMS': '1000',
    }

    request = factory.post('/admin/ventas/comanda/add/?venta_reserva=4971&_popup=1',
                          data=post_data)
    request.user = User.objects.get(username='Deborah')
    request.GET = QueryDict('venta_reserva=4971&_popup=1')

    # Configurar messages
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print("1. Request configurado:")
    print(f"   - Usuario: {request.user}")
    print(f"   - POST data keys: {list(post_data.keys())}")
    print(f"   - GET params: {request.GET}")

    # Probar el changeform_view completo
    print("\n2. Ejecutando changeform_view...")
    try:
        # Obtener response
        response = admin.add_view(request)

        print(f"\n   ✅ Response obtenido: {type(response)}")
        print(f"   Status code: {getattr(response, 'status_code', 'N/A')}")

        # Si es redirect o contenido
        if hasattr(response, 'content'):
            content = response.content.decode('utf-8', errors='ignore')
            if 'errorlist' in content:
                print("\n   ❌ Errores de formulario encontrados:")
                # Buscar errores
                import re
                errors = re.findall(r'<ul class="errorlist.*?</ul>', content, re.DOTALL)
                for error in errors[:5]:  # Mostrar primeros 5 errores
                    print(f"      {error}")
            elif 'window.close()' in content:
                print("   ✅ Popup cerrado correctamente")
            else:
                print(f"   Contenido response (primeros 500 chars):\n{content[:500]}")

    except Exception as e:
        print(f"\n   ❌ ERROR en add_view: {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")
        print("\n   Traceback completo:")
        traceback.print_exc()

except Exception as e:
    print(f"\n❌ ERROR GENERAL: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN DEL DEBUG ===")