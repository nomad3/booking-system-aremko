import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from ventas.admin import ComandaAdmin
from ventas.models import Comanda
from django.http import QueryDict

print("=== TEST CON SUPERUSUARIO ===\n")

try:
    # Buscar un superusuario
    superuser = User.objects.filter(is_superuser=True).first()
    if not superuser:
        print("❌ No hay superusuarios en el sistema")
        exit(1)

    print(f"Usando superusuario: {superuser.username}")

    # Setup admin
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Datos
    vr_id = 39

    # POST data
    post_data = {
        'venta_reserva': str(vr_id),
        'notas_generales': 'Test con superusuario',
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

    # Crear request
    request = factory.post(
        f'/admin/ventas/comanda/add/?venta_reserva={vr_id}&_popup=1',
        data=post_data
    )
    request.user = superuser
    request.GET = QueryDict(f'venta_reserva={vr_id}&_popup=1')

    # Messages
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print("\nEjecutando admin.add_view() con superusuario...")

    # Llamar add_view
    response = admin.add_view(request)

    print(f"\nResponse type: {type(response)}")
    print(f"Status code: {getattr(response, 'status_code', 'N/A')}")

    if hasattr(response, 'content'):
        content = response.content.decode('utf-8', errors='ignore')
        if 'window.close()' in content:
            print("✅ ÉXITO - Popup cerrado correctamente!")
            # Buscar y eliminar la comanda creada
            comandas = Comanda.objects.filter(
                notas_generales='Test con superusuario'
            ).order_by('-id')
            if comandas:
                for c in comandas:
                    print(f"   Comanda creada: ID={c.id}")
                    c.delete()
                    print("   (eliminada)")
        elif '403' in str(response.status_code):
            print("❌ Error 403 incluso con superusuario!")
        else:
            print(f"Respuesta inesperada. Primeros 300 chars:\n{content[:300]}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===")