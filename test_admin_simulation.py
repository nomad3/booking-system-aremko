import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from ventas.admin import ComandaAdmin
from ventas.models import Comanda, VentaReserva

print("=== SIMULACIÓN COMPLETA DEL ADMIN ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Usar datos reales
    vr_id = 39  # Maria Jose Rodriguez
    user_id = 7  # Ernesto

    print(f"Usando VentaReserva ID={vr_id}, Usuario ID={user_id}\n")

    # Crear request POST simulando el formulario
    post_data = {
        'venta_reserva': str(vr_id),
        'notas_generales': 'Test simulación admin',
        'estado': 'pendiente',
        'usuario_solicita': str(user_id),
        'usuario_procesa': str(user_id),
        # Popup flag
        '_popup': '1',
        '_save': 'Guardar',
        # Formset vacío
        'detalles-TOTAL_FORMS': '0',
        'detalles-INITIAL_FORMS': '0',
        'detalles-MIN_NUM_FORMS': '0',
        'detalles-MAX_NUM_FORMS': '1000',
    }

    request = factory.post(f'/admin/ventas/comanda/add/?venta_reserva={vr_id}&_popup=1',
                          data=post_data)
    request.user = User.objects.get(id=user_id)

    # Configurar messages
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print("1. Obteniendo formulario...")
    ModelForm = admin.get_form(request, None)
    print("   ✅ Form class obtenido")

    print("\n2. Creando formulario con datos...")
    form = ModelForm(data=post_data)

    print("\n3. Validando formulario...")
    if form.is_valid():
        print("   ✅ Formulario válido")

        print("\n4. Guardando con save_model...")
        obj = form.save(commit=False)
        admin.save_model(request, obj, form, False)
        print(f"   ✅ Comanda guardada: ID={obj.id}")

        # Limpiar
        obj.delete()
        print("   ✅ Comanda eliminada")

    else:
        print("   ❌ Formulario inválido")
        for field, errors in form.errors.items():
            print(f"      - {field}: {errors}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DE LA SIMULACIÓN ===")