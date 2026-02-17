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

print("=== TEST COMPLETO ADD_VIEW DEL ADMIN ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Datos reales
    vr_id = 39
    user = User.objects.get(id=7)  # Ernesto

    # POST data
    post_data = {
        'venta_reserva': str(vr_id),
        'notas_generales': 'Test add_view completo',
        'estado': 'pendiente',
        'usuario_solicita': str(user.id),
        'usuario_procesa': str(user.id),
        '_popup': '1',
        '_save': 'Guardar',
        # Formset management
        'detalles-TOTAL_FORMS': '0',
        'detalles-INITIAL_FORMS': '0',
        'detalles-MIN_NUM_FORMS': '0',
        'detalles-MAX_NUM_FORMS': '1000',
        'detalles-__prefix__-producto': '',
        'detalles-__prefix__-cantidad': '',
        'detalles-__prefix__-especificaciones': '',
        'detalles-__prefix__-precio_unitario': '',
    }

    # Crear request
    request = factory.post(
        f'/admin/ventas/comanda/add/?venta_reserva={vr_id}&_popup=1',
        data=post_data
    )
    request.user = user
    request.GET = QueryDict(f'venta_reserva={vr_id}&_popup=1')

    # Configurar session y messages
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print(f"Usuario: {request.user.username}")
    print(f"VentaReserva ID: {vr_id}")
    print(f"Es popup: {request.GET.get('_popup')}")

    print("\nEjecutando admin.add_view()...")

    # Llamar add_view (esto es lo que Django hace cuando accedes a /admin/ventas/comanda/add/)
    response = admin.add_view(request)

    print(f"\nResponse type: {type(response)}")
    print(f"Status code: {getattr(response, 'status_code', 'N/A')}")

    if hasattr(response, 'content'):
        content = response.content.decode('utf-8', errors='ignore')[:500]
        if 'window.close()' in content:
            print("✅ Popup cerrado correctamente - Comanda creada!")
        elif '<ul class="errorlist' in content:
            print("❌ Hay errores en el formulario")
            # Buscar errores
            import re
            errors = re.findall(r'<ul class="errorlist.*?</ul>', content, re.DOTALL)
            for error in errors[:3]:
                print(f"   Error: {error}")
        else:
            print(f"Contenido (primeros 200 chars):\n{content[:200]}")

    # Verificar si se creó alguna comanda
    comandas = Comanda.objects.filter(
        venta_reserva_id=vr_id,
        notas_generales__contains='Test add_view'
    ).order_by('-id')

    if comandas:
        print(f"\n✅ Comandas creadas: {comandas.count()}")
        for c in comandas:
            print(f"   - ID={c.id}, creada: {c.fecha_solicitud}")
            c.delete()
            print(f"     (eliminada)")
    else:
        print("\n⚠️  No se encontraron comandas creadas")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}")
    print(f"Mensaje: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===")