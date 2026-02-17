import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User

print("=== TEST DE VARIACIONES ===\n")

try:
    client = Client()
    superuser = User.objects.filter(is_superuser=True).first()
    client.force_login(superuser)

    # Test 1: Sin parámetros
    print("1. GET sin parámetros:")
    response = client.get('/admin/ventas/comanda/add/')
    print(f"   Status: {response.status_code}")
    if response.status_code == 400:
        print(f"   Contenido: {response.content.decode('utf-8')[:200]}")

    # Test 2: Solo con popup
    print("\n2. GET solo con _popup:")
    response = client.get('/admin/ventas/comanda/add/?_popup=1')
    print(f"   Status: {response.status_code}")

    # Test 3: Solo con venta_reserva
    print("\n3. GET solo con venta_reserva:")
    response = client.get('/admin/ventas/comanda/add/?venta_reserva=39')
    print(f"   Status: {response.status_code}")

    # Test 4: Con ambos parámetros
    print("\n4. GET con ambos parámetros:")
    response = client.get('/admin/ventas/comanda/add/?_popup=1&venta_reserva=39')
    print(f"   Status: {response.status_code}")

    # Test 5: Verificar que VentaReserva 39 existe
    print("\n5. Verificando VentaReserva 39:")
    from ventas.models import VentaReserva
    vr = VentaReserva.objects.filter(id=39).first()
    if vr:
        print(f"   ✅ Existe: {vr}")
    else:
        print("   ❌ NO existe")

    # Test 6: Probar con otra VentaReserva
    print("\n6. Probando con primera VentaReserva disponible:")
    vr = VentaReserva.objects.first()
    if vr:
        response = client.get(f'/admin/ventas/comanda/add/?_popup=1&venta_reserva={vr.id}')
        print(f"   VentaReserva ID={vr.id}, Status: {response.status_code}")

    # Test 7: Ver si hay algún error específico en el response
    if response.status_code == 400:
        print("\n7. Contenido del Error 400:")
        content = response.content.decode('utf-8')
        if 'Bad Request' in content:
            print("   Mensaje genérico de Bad Request")
        else:
            print(f"   {content[:500]}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===")