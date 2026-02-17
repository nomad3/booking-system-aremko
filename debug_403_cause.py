import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory, Client
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from ventas.admin import ComandaAdmin
from ventas.models import Comanda
from django.middleware.csrf import get_token

print("=== INVESTIGAR CAUSA DEL ERROR 403 ===\n")

try:
    # Test 1: Verificar si el admin está registrado
    print("1. Verificando registro del admin...")
    from django.contrib import admin as django_admin
    if Comanda in django_admin.site._registry:
        print("   ✅ Comanda está registrada en el admin")
    else:
        print("   ❌ Comanda NO está registrada en el admin")

    # Test 2: Verificar métodos del admin
    print("\n2. Verificando métodos del ComandaAdmin...")
    site = AdminSite()
    admin_obj = ComandaAdmin(Comanda, site)

    methods_to_check = ['has_add_permission', 'has_change_permission', 'has_view_permission']

    # Crear un request simple
    factory = RequestFactory()
    request = factory.get('/')
    request.user = User.objects.filter(is_superuser=True).first()

    for method in methods_to_check:
        if hasattr(admin_obj, method):
            try:
                result = getattr(admin_obj, method)(request)
                print(f"   - {method}: {'✅ True' if result else '❌ False'}")
            except Exception as e:
                print(f"   - {method}: ❌ Error: {str(e)}")

    # Test 3: Probar con Django test client (más realista)
    print("\n3. Probando con Django test client...")
    client = Client()
    superuser = User.objects.filter(is_superuser=True).first()

    # Login
    logged_in = client.force_login(superuser)
    print(f"   - Login como {superuser.username}")

    # Intentar acceder a la página de add
    response = client.get('/admin/ventas/comanda/add/')
    print(f"   - GET /admin/ventas/comanda/add/: Status {response.status_code}")

    # Intentar con popup
    response = client.get('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39')
    print(f"   - GET con popup: Status {response.status_code}")

    # Test 4: Verificar configuración de MIDDLEWARE
    print("\n4. Middlewares activos:")
    from django.conf import settings
    for middleware in settings.MIDDLEWARE[:5]:
        print(f"   - {middleware}")

    # Test 5: Verificar si hay decoradores personalizados
    print("\n5. Verificando decoradores en add_view...")
    if hasattr(admin_obj.add_view, '__wrapped__'):
        print("   ⚠️  add_view tiene decoradores adicionales")
    else:
        print("   ✅ add_view no tiene decoradores adicionales")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DE LA INVESTIGACIÓN ===")