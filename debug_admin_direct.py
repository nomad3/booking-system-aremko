# Debug directo del formulario del admin
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
import traceback

print("=== DEBUG FORMULARIO ADMIN COMANDA ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)
    factory = RequestFactory()

    # Crear request con popup
    request = factory.get('/admin/ventas/comanda/add/?venta_reserva=4971&_popup=1')
    request.user = User.objects.get(username='Deborah')

    # Agregar messages (requerido por admin)
    setattr(request, 'session', {})
    messages = FallbackStorage(request)
    setattr(request, '_messages', messages)

    print("1. Obteniendo formulario...")

    # Obtener el form class
    ModelForm = admin.get_form(request)
    print("   ✅ Form class obtenido")

    # Ver campos del formulario
    print("\n2. Campos del formulario:")
    if hasattr(ModelForm, '_meta'):
        print(f"   Model: {ModelForm._meta.model}")
        if hasattr(ModelForm._meta, 'fields'):
            print(f"   Fields: {ModelForm._meta.fields}")
        if hasattr(ModelForm._meta, 'exclude'):
            print(f"   Exclude: {ModelForm._meta.exclude}")

    # Intentar crear instancia del formulario
    print("\n3. Creando instancia del formulario...")
    form = ModelForm()
    print("   ✅ Formulario creado")

    # Ver campos iniciales
    print("\n4. Valores iniciales:")
    for field_name, field in form.fields.items():
        if hasattr(field, 'initial') and field.initial is not None:
            print(f"   {field_name}: {field.initial}")

    # Verificar fieldsets
    print("\n5. Verificando fieldsets...")
    fieldsets = admin.get_fieldsets(request, None)
    for name, options in fieldsets:
        print(f"\n   {name}:")
        fields = options.get('fields', [])
        print(f"   Fields: {fields}")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

print("\n=== FIN DEL DEBUG ===")