# Script para debuggear el error 500 específico del admin
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from ventas.admin import ComandaAdmin
from ventas.models import Comanda, DetalleComanda, VentaReserva, Producto
import traceback

print("=== DEBUG ADMIN ERROR 500 ===\n")

try:
    # Configurar el entorno del admin
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)

    # Crear request mock
    factory = RequestFactory()
    request = factory.get('/admin/ventas/comanda/add/?venta_reserva=4971&_popup=1')
    request.user = User.objects.get(username='Deborah')

    print("1. Admin configurado correctamente")
    print(f"   - Usuario: {request.user.username}")
    print(f"   - Es staff: {request.user.is_staff}")
    print(f"   - Es superusuario: {request.user.is_superuser}")

    # Verificar métodos del admin
    print("\n2. Verificando métodos del admin:")
    print(f"   - save_model existe: {hasattr(admin, 'save_model')}")
    print(f"   - save_formset existe: {hasattr(admin, 'save_formset')}")
    print(f"   - get_form existe: {hasattr(admin, 'get_form')}")

    # Probar get_form
    print("\n3. Probando get_form...")
    try:
        form_class = admin.get_form(request)
        print("   ✅ get_form funciona")

        # Ver campos iniciales
        if hasattr(form_class, 'base_fields'):
            if 'usuario_solicita' in form_class.base_fields:
                inicial = form_class.base_fields['usuario_solicita'].initial
                print(f"   - usuario_solicita inicial: {inicial}")
            if 'usuario_procesa' in form_class.base_fields:
                inicial = form_class.base_fields['usuario_procesa'].initial
                print(f"   - usuario_procesa inicial: {inicial}")

    except Exception as e:
        print(f"   ❌ Error en get_form: {str(e)}")
        traceback.print_exc()

    # Probar campos problemáticos
    print("\n4. Verificando campos problemáticos:")

    # Verificar readonly_fields
    if hasattr(admin, 'readonly_fields'):
        print(f"   - Readonly fields: {admin.readonly_fields}")

    # Verificar campos con métodos display
    for attr_name in dir(admin):
        if attr_name.endswith('_display'):
            print(f"   - Método display encontrado: {attr_name}")

    # Verificar inlines
    if hasattr(admin, 'inlines'):
        print(f"   - Inlines: {[inline.__name__ for inline in admin.inlines]}")

    print("\n✅ Admin parece estar configurado correctamente")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN DEL DEBUG ===")