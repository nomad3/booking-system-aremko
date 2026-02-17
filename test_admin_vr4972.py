import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from ventas.admin import VentaReservaAdmin
from ventas.models import VentaReserva
import traceback

print("=== TEST ADMIN VentaReserva 4972 ===\n")

try:
    # Setup
    site = AdminSite()
    admin = VentaReservaAdmin(VentaReserva, site)
    factory = RequestFactory()

    # Crear request
    request = factory.get(f'/admin/ventas/ventareserva/4972/change/')
    request.user = User.objects.filter(is_superuser=True).first()

    print(f"Usuario: {request.user}")

    # Obtener la instancia
    vr = VentaReserva.objects.get(id=4972)
    print(f"VentaReserva: {vr}")

    # Probar métodos del admin que podrían fallar
    print("\n1. Probando métodos de display del admin...")

    # Lista de métodos que el admin podría usar
    display_methods = [
        'cliente_info_display',
        'fecha_display',
        'estado_display',
        'total_display',
        'pagado_display',
        'saldo_display',
        'productos_display',
        'servicios_display',
        'comandas_display',  # Este podría ser el problema
    ]

    for method_name in display_methods:
        if hasattr(admin, method_name):
            try:
                method = getattr(admin, method_name)
                result = method(vr)
                print(f"   ✅ {method_name}: OK (resultado: {str(result)[:50]}...)")
            except Exception as e:
                print(f"   ❌ {method_name}: ERROR - {type(e).__name__}: {str(e)}")
                traceback.print_exc()

    # Probar get_form
    print("\n2. Probando get_form...")
    try:
        form_class = admin.get_form(request, vr)
        print("   ✅ get_form: OK")
    except Exception as e:
        print(f"   ❌ get_form: ERROR - {str(e)}")
        traceback.print_exc()

    # Probar change_view directamente
    print("\n3. Probando change_view...")
    try:
        # Agregar atributos necesarios al request
        request.session = {}
        from django.contrib.messages.storage.fallback import FallbackStorage
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)

        response = admin.change_view(request, '4972')
        print(f"   ✅ change_view: {type(response)} - Status: {getattr(response, 'status_code', 'N/A')}")
    except Exception as e:
        print(f"   ❌ change_view: ERROR - {type(e).__name__}")
        print(f"   Mensaje: {str(e)}")
        traceback.print_exc()

    # Verificar inlines
    print("\n4. Verificando inlines...")
    if hasattr(admin, 'inlines'):
        for inline_class in admin.inlines:
            print(f"   - {inline_class.__name__}")
            try:
                inline = inline_class(VentaReserva, site)
                # Verificar si el inline puede causar problemas
                qs = inline.get_queryset(request)
                if hasattr(inline, 'model'):
                    count = qs.filter(venta_reserva_id=4972).count()
                    print(f"     Registros: {count}")
            except Exception as e:
                print(f"     ❌ Error: {str(e)}")

except Exception as e:
    print(f"\n❌ ERROR GENERAL: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN TEST ===")