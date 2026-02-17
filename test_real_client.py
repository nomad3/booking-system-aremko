import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

print("=== TEST CON CLIENT REAL ===\n")

try:
    # Usar Django test client
    client = Client()

    # Buscar usuarios para probar
    superuser = User.objects.filter(is_superuser=True).first()
    ernesto = User.objects.get(username='Ernesto')

    print("1. Probando con superusuario...")
    client.force_login(superuser)

    # GET la página
    response = client.get('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39')
    print(f"   GET Status: {response.status_code}")

    if response.status_code == 200:
        print("   ✅ Página cargó correctamente")

        # Obtener CSRF token del formulario
        content = response.content.decode('utf-8')
        import re
        csrf_match = re.search(r'name=["\']csrfmiddlewaretoken["\'] value=["\']([^"\']+)["\']', content)
        csrf_token = csrf_match.group(1) if csrf_match else None

        if csrf_token:
            print(f"   CSRF Token encontrado: {csrf_token[:20]}...")

            # POST para crear comanda
            post_data = {
                'csrfmiddlewaretoken': csrf_token,
                'venta_reserva': '39',
                'notas_generales': 'Test con client real',
                'estado': 'pendiente',
                'usuario_solicita': str(superuser.id),
                'usuario_procesa': str(superuser.id),
                '_popup': '1',
                '_save': 'Guardar',
                # Formset
                'detalles-TOTAL_FORMS': '0',
                'detalles-INITIAL_FORMS': '0',
                'detalles-MIN_NUM_FORMS': '0',
                'detalles-MAX_NUM_FORMS': '1000',
            }

            response = client.post('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39',
                                 data=post_data,
                                 follow=True)

            print(f"\n   POST Status: {response.status_code}")

            if response.status_code == 200:
                content = response.content.decode('utf-8')
                if 'window.close()' in content:
                    print("   ✅ ÉXITO - Comanda creada y popup cerrado!")
                elif 'errorlist' in content:
                    print("   ❌ Errores de validación en el formulario")
                else:
                    print("   ❓ Respuesta inesperada")
    else:
        print(f"   ❌ Error {response.status_code}")

    # Probar también con Ernesto
    print("\n2. Probando con Ernesto...")
    client.force_login(ernesto)
    response = client.get('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39')
    print(f"   GET Status: {response.status_code}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

# Limpiar comandas de prueba
from ventas.models import Comanda
Comanda.objects.filter(notas_generales='Test con client real').delete()

print("\n=== FIN DEL TEST ===")