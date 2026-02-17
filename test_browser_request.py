import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
import re

print("=== SIMULAR REQUEST DEL NAVEGADOR ===\n")

try:
    # Usar Client que maneja cookies, sesión, etc.
    client = Client()

    # Login como admin
    superuser = User.objects.filter(is_superuser=True).first()
    client.force_login(superuser)
    print(f"Login como: {superuser.username}")

    # Intentar acceder a la lista de VentaReserva
    print("\n1. Accediendo a la lista...")
    response = client.get('/admin/ventas/ventareserva/')
    print(f"   Status: {response.status_code}")

    # Intentar acceder a VentaReserva 39 (que sabemos que funciona)
    print("\n2. Accediendo a VentaReserva 39...")
    response = client.get('/admin/ventas/ventareserva/39/change/')
    print(f"   Status: {response.status_code}")

    # Intentar acceder a VentaReserva 4972
    print("\n3. Accediendo a VentaReserva 4972...")
    response = client.get('/admin/ventas/ventareserva/4972/change/')
    print(f"   Status: {response.status_code}")

    if response.status_code != 200:
        print(f"\n   ❌ Error {response.status_code}")

        # Si es 500, intentar obtener el error
        if response.status_code == 500:
            content = response.content.decode('utf-8', errors='ignore')

            # Buscar mensaje de error
            if 'exception_value' in content:
                match = re.search(r'exception_value">(.*?)</pre>', content, re.DOTALL)
                if match:
                    print(f"\n   Excepción: {match.group(1)[:200]}")

            # Si DEBUG está activado, habrá más info
            if '<div class="traceback">' in content:
                print("\n   Traceback disponible en el HTML")

            # Guardar el HTML completo para análisis
            with open('/tmp/error_4972.html', 'w') as f:
                f.write(content)
            print("\n   HTML completo guardado en: /tmp/error_4972.html")

    # Probar con headers específicos del navegador
    print("\n4. Probando con headers de navegador real...")
    response = client.get(
        '/admin/ventas/ventareserva/4972/change/',
        HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        HTTP_ACCEPT='text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        HTTP_ACCEPT_LANGUAGE='es-ES,es;q=0.9,en;q=0.8',
        HTTP_ACCEPT_ENCODING='gzip, deflate, br',
        HTTP_CONNECTION='keep-alive',
        HTTP_UPGRADE_INSECURE_REQUESTS='1'
    )
    print(f"   Status con headers: {response.status_code}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN TEST ===")