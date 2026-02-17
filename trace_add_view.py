import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from ventas.admin import ComandaAdmin
from ventas.models import Comanda
import inspect

print("=== RASTREAR add_view ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Inspeccionar add_view
    print("1. Inspeccionando add_view...")
    print(f"   - Tipo: {type(admin.add_view)}")
    print(f"   - Módulo: {getattr(admin.add_view, '__module__', 'N/A')}")

    # Ver si tiene decoradores
    if hasattr(admin.add_view, '__wrapped__'):
        print("   - Tiene __wrapped__ (decoradores)")
        wrapped = admin.add_view.__wrapped__
        print(f"   - Wrapped type: {type(wrapped)}")

    # Ver el código fuente si es posible
    try:
        source = inspect.getsource(admin.add_view)
        print("\n2. Código fuente de add_view (primeras 5 líneas):")
        lines = source.split('\n')[:5]
        for line in lines:
            print(f"   {line}")
    except:
        print("\n2. No se puede obtener el código fuente")

    # Probar llamar add_view paso a paso
    print("\n3. Llamando add_view con monitoreo...")

    # Crear request
    request = factory.get('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39')
    request.user = User.objects.filter(is_superuser=True).first()

    # Agregar atributos que pueden faltar
    request.session = {}
    request._messages = None

    # Intentar add_view con manejo de errores detallado
    try:
        response = admin.add_view(request)
        print(f"   ✅ Respuesta: {type(response)}, Status: {getattr(response, 'status_code', 'N/A')}")
    except AttributeError as e:
        print(f"   ❌ AttributeError: {str(e)}")
        print("      Probablemente falta un atributo en el request")
    except Exception as e:
        print(f"   ❌ {type(e).__name__}: {str(e)}")

    # Ver qué métodos se llaman desde add_view
    print("\n4. Métodos relacionados en ComandaAdmin:")
    methods = ['changeform_view', '_changeform_view', 'get_form', 'get_fieldsets']
    for method in methods:
        if hasattr(admin, method):
            print(f"   - {method}: existe")

    # Verificar la cadena de herencia
    print("\n5. Cadena de herencia:")
    for cls in admin.__class__.__mro__:
        print(f"   - {cls}")
        if hasattr(cls, 'add_view'):
            print(f"     (define add_view)")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN ===")