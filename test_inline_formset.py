import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.test import RequestFactory
from django.contrib.auth.models import User
from django.contrib.admin.sites import AdminSite
from ventas.admin import ComandaAdmin, DetalleComandaInline
from ventas.models import Comanda
from django.forms.models import inlineformset_factory

print("=== TEST INLINE FORMSET ===\n")

try:
    # Setup
    site = AdminSite()
    admin = ComandaAdmin(Comanda, site)

    print("1. Verificando configuración de inlines...")
    print(f"   Inlines: {[inline.__name__ for inline in admin.inlines]}")

    # Verificar DetalleComandaInline
    inline = DetalleComandaInline(Comanda, site)
    print(f"\n2. DetalleComandaInline configuración:")
    print(f"   - extra: {inline.extra}")
    print(f"   - min_num: {getattr(inline, 'min_num', 0)}")
    print(f"   - max_num: {getattr(inline, 'max_num', None)}")
    print(f"   - fields: {inline.fields}")
    print(f"   - readonly_fields: {inline.readonly_fields}")
    print(f"   - autocomplete_fields: {inline.autocomplete_fields}")

    # Crear formset factory
    print("\n3. Creando formset factory...")
    from ventas.models import DetalleComanda
    FormSet = inlineformset_factory(
        Comanda,
        DetalleComanda,
        fields=inline.fields,
        extra=inline.extra,
        can_delete=True
    )
    print("   ✅ Formset factory creado")

    # Probar formset vacío
    print("\n4. Probando formset vacío...")
    formset = FormSet(data={
        'detalles-TOTAL_FORMS': '0',
        'detalles-INITIAL_FORMS': '0',
        'detalles-MIN_NUM_FORMS': '0',
        'detalles-MAX_NUM_FORMS': '1000',
    })

    if formset.is_valid():
        print("   ✅ Formset vacío es válido")
    else:
        print("   ❌ Formset vacío no es válido")
        print(f"   Errores: {formset.errors}")
        print(f"   Non-form errors: {formset.non_form_errors()}")

    print("\n✅ No hay problemas evidentes con los inlines")

except Exception as e:
    print(f"\n❌ ERROR: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===")