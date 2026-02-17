import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from ventas.admin import ComandaAdmin
from ventas.models import Comanda
from django.contrib.admin.sites import AdminSite

print("=== OBTENER ERROR REAL ===\n")

try:
    # Habilitar DEBUG temporalmente para ver errores
    from django.conf import settings
    original_debug = settings.DEBUG
    settings.DEBUG = True

    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Crear request
    request = factory.get('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39')
    request.user = User.objects.filter(is_superuser=True).first()

    print(f"Usuario: {request.user}")
    print(f"GET params: {request.GET}")

    # Intentar obtener el formulario directamente
    print("\nIntentando obtener el formulario...")
    try:
        # Llamar _changeform_view directamente para capturar el error
        response = admin._changeform_view(request, None, '', None)
        print(f"Response: {type(response)}, Status: {getattr(response, 'status_code', 'N/A')}")
    except Exception as e:
        print(f"\n❌ ERROR en _changeform_view:")
        print(f"   Tipo: {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")
        import traceback
        traceback.print_exc()

    # Restaurar DEBUG
    settings.DEBUG = original_debug

except Exception as e:
    print(f"\n❌ ERROR GENERAL: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN ===")