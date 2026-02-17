# Debug para validación del formulario
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
from django.forms.models import modelform_factory
import traceback

print("=== DEBUG VALIDACIÓN FORMULARIO COMANDA ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Request simulado
    request = factory.get('/admin/ventas/comanda/add/?venta_reserva=4971&_popup=1')
    request.user = User.objects.get(username='Deborah')

    # Messages
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print("1. Obteniendo fieldsets para creación...")
    fieldsets = admin.get_fieldsets(request, None)
    all_fields = []
    for name, options in fieldsets:
        print(f"\n   {name or 'Información General'}:")
        fields = options.get('fields', [])
        for field in fields:
            if isinstance(field, tuple):
                for f in field:
                    all_fields.append(f)
                    print(f"      - {f}")
            else:
                all_fields.append(field)
                print(f"      - {field}")

    print(f"\n2. Campos totales en fieldsets: {len(all_fields)}")

    # Obtener el ModelForm
    print("\n3. Analizando ModelForm...")
    ModelForm = admin.get_form(request, None)

    # Ver Meta del form
    if hasattr(ModelForm, '_meta'):
        print(f"   - Model: {ModelForm._meta.model.__name__}")
        if hasattr(ModelForm._meta, 'fields'):
            print(f"   - Fields explícitos: {ModelForm._meta.fields}")
        if hasattr(ModelForm._meta, 'exclude'):
            print(f"   - Exclude: {ModelForm._meta.exclude}")

    # Crear instancia del form sin datos para ver campos
    form = ModelForm()
    print(f"\n4. Campos en el formulario: {len(form.fields)}")

    # Verificar campos requeridos vs readonly
    print("\n5. Análisis de campos:")
    problematic_fields = []

    for field_name, field in form.fields.items():
        is_required = field.required
        is_readonly = field_name in admin.readonly_fields
        is_auto = False

        # Verificar si es un campo auto
        if hasattr(Comanda, field_name):
            model_field = Comanda._meta.get_field(field_name)
            is_auto = getattr(model_field, 'auto_now', False) or getattr(model_field, 'auto_now_add', False)

        if is_required and is_readonly:
            problematic_fields.append(field_name)
            print(f"   ⚠️  {field_name}: required={is_required}, readonly={is_readonly}, auto={is_auto}")
        elif field_name in ['fecha_solicitud', 'hora_solicitud', 'created_at', 'updated_at']:
            print(f"   📅 {field_name}: required={is_required}, readonly={is_readonly}, auto={is_auto}")

    if problematic_fields:
        print(f"\n   ❌ Campos problemáticos encontrados: {problematic_fields}")

    # Probar con datos mínimos
    print("\n6. Probando validación con datos mínimos...")
    test_data = {
        'venta_reserva': '4971',
        'notas_generales': 'Test',
        'estado': 'pendiente',
        'usuario_solicita': str(request.user.id),
        'usuario_procesa': str(request.user.id),
        # NO incluir campos auto_now_add
        # Formset vacío
        'detalles-TOTAL_FORMS': '0',
        'detalles-INITIAL_FORMS': '0',
        'detalles-MIN_NUM_FORMS': '0',
        'detalles-MAX_NUM_FORMS': '1000',
    }

    test_form = ModelForm(data=test_data)
    if test_form.is_valid():
        print("   ✅ Formulario válido con datos mínimos")
    else:
        print("   ❌ Formulario inválido")
        for field, errors in test_form.errors.items():
            print(f"      - {field}: {errors}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN DEL DEBUG ===")