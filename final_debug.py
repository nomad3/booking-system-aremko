import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from ventas.admin import ComandaAdmin
from ventas.models import Comanda
from django.urls import reverse

print("=== DEBUG FINAL - DIFERENCIAS ===\n")

try:
    # Setup
    superuser = User.objects.filter(is_superuser=True).first()

    # Test 1: URL reversa
    print("1. Verificando URL del admin...")
    try:
        url = reverse('admin:ventas_comanda_add')
        print(f"   URL: {url}")
    except Exception as e:
        print(f"   ❌ Error al resolver URL: {str(e)}")

    # Test 2: Cliente con debug
    print("\n2. Cliente con debug habilitado...")
    from django.conf import settings
    original_debug = settings.DEBUG
    settings.DEBUG = True

    client = Client()
    client.force_login(superuser)

    # Hacer request y capturar el error
    response = client.get('/admin/ventas/comanda/add/')
    print(f"   Status: {response.status_code}")

    if hasattr(response, 'context') and response.context:
        if 'exception' in response.context:
            print(f"   Exception: {response.context['exception']}")

    # Si es 400, ver el contenido completo
    if response.status_code == 400:
        content = response.content.decode('utf-8')
        # Buscar mensaje de error específico
        import re
        error_match = re.search(r'<p>(.*?)</p>', content)
        if error_match:
            print(f"   Mensaje: {error_match.group(1)}")

    settings.DEBUG = original_debug

    # Test 3: Verificar ALLOWED_HOSTS y CSRF
    print("\n3. Configuración de seguridad...")
    print(f"   DEBUG: {settings.DEBUG}")
    print(f"   ALLOWED_HOSTS: {settings.ALLOWED_HOSTS[:3]}...")  # Primeros 3
    print(f"   CSRF_COOKIE_SECURE: {getattr(settings, 'CSRF_COOKIE_SECURE', 'No definido')}")
    print(f"   SESSION_COOKIE_SECURE: {getattr(settings, 'SESSION_COOKIE_SECURE', 'No definido')}")

    # Test 4: Middleware problemático
    print("\n4. Verificando middleware...")
    for i, middleware in enumerate(settings.MIDDLEWARE):
        if any(x in middleware.lower() for x in ['security', 'csrf', 'auth', 'cors']):
            print(f"   [{i}] {middleware}")

    # Test 5: Admin site
    print("\n5. Admin site registrado...")
    from django.contrib import admin
    if Comanda in admin.site._registry:
        admin_class = admin.site._registry[Comanda]
        print(f"   ✅ Comanda registrada con: {admin_class.__class__}")
    else:
        print("   ❌ Comanda NO registrada")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEBUG FINAL ===")