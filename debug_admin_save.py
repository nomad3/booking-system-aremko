# Script para capturar el error exacto al guardar una comanda
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from ventas.admin import ComandaAdmin
from ventas.models import Comanda, VentaReserva, Cliente
import traceback
from datetime import datetime

print("=== DEBUG COMPLETO GUARDADO COMANDA ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Crear request POST simulando el formulario
    request = factory.post('/admin/ventas/comanda/add/?venta_reserva=4971&_popup=1')
    request.user = User.objects.get(username='Deborah')

    # Agregar session y messages (requerido por admin)
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print("1. Verificando VentaReserva...")
    try:
        venta = VentaReserva.objects.get(id=4971)
        print(f"   ✅ VentaReserva encontrada: {venta}")
        print(f"      - Cliente: {venta.cliente}")
        print(f"      - Estado: {venta.estado}")
    except VentaReserva.DoesNotExist:
        print("   ❌ VentaReserva 4971 no existe")

    print("\n2. Obteniendo formulario...")
    ModelForm = admin.get_form(request)

    # Datos mínimos para crear una comanda
    form_data = {
        'venta_reserva': '4971',
        'mesa_numero': '1',
        'descripcion': 'Comanda de prueba',
        'estado': 'pendiente',
        'usuario_solicita': str(request.user.id),
        'usuario_procesa': str(request.user.id),
        # No incluir campos auto_now/auto_now_add
        'fecha_solicitud_0': datetime.now().strftime('%Y-%m-%d'),  # Fecha
        'fecha_solicitud_1': datetime.now().strftime('%H:%M:%S'),  # Hora
        'hora_solicitud': datetime.now().strftime('%H:%M:%S'),
        # Formset vacío para los detalles
        'detalles-TOTAL_FORMS': '0',
        'detalles-INITIAL_FORMS': '0',
        'detalles-MIN_NUM_FORMS': '0',
        'detalles-MAX_NUM_FORMS': '1000',
    }

    print("\n3. Creando formulario con datos...")
    form = ModelForm(data=form_data)

    print("\n4. Validando formulario...")
    if form.is_valid():
        print("   ✅ Formulario válido")

        print("\n5. Intentando guardar...")
        try:
            # Simular el guardado del admin
            obj = form.save(commit=False)

            # Llamar save_model como lo haría el admin
            admin.save_model(request, obj, form, False)

            print("   ✅ Comanda guardada exitosamente")
            print(f"      - ID: {obj.id}")
            print(f"      - Estado: {obj.estado}")

        except Exception as e:
            print(f"   ❌ Error al guardar: {type(e).__name__}: {str(e)}")
            traceback.print_exc()

    else:
        print("   ❌ Formulario inválido")
        print("   Errores:")
        for field, errors in form.errors.items():
            print(f"      - {field}: {errors}")

    # Verificar también el proceso completo del admin
    print("\n6. Probando el flujo completo del admin...")

    # Ver si hay algún problema con get_fieldsets durante el guardado
    try:
        fieldsets = admin.get_fieldsets(request, None)
        print("   ✅ get_fieldsets funciona para creación")
    except Exception as e:
        print(f"   ❌ Error en get_fieldsets: {str(e)}")
        traceback.print_exc()

    # Verificar los inlines
    print("\n7. Verificando inlines...")
    if hasattr(admin, 'inlines'):
        for inline_class in admin.inlines:
            print(f"   - {inline_class.__name__}")
            inline = inline_class(Comanda, site)

            # Verificar si el inline puede causar problemas
            if hasattr(inline, 'extra'):
                print(f"     Extra forms: {inline.extra}")
            if hasattr(inline, 'min_num'):
                print(f"     Min num: {inline.min_num}")

except Exception as e:
    print(f"\n❌ ERROR GENERAL: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN DEL DEBUG ===")