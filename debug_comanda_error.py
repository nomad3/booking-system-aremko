# Script para debuggear el error 500 en comandas
# Ejecutar con: python manage.py shell < debug_comanda_error.py

from django.contrib.auth.models import User
from ventas.models import Comanda, DetalleComanda, VentaReserva, Producto
from ventas.admin import ComandaAdmin
from django.contrib.admin.sites import site
import traceback

print("=== DEBUG ERROR 500 EN COMANDAS ===")
print()

# 1. Verificar configuración del admin
print("1. Verificando registro del ComandaAdmin...")
try:
    admin_class = site._registry.get(Comanda)
    if admin_class:
        print("✅ ComandaAdmin está registrado")
        print(f"   Clase: {admin_class.__class__.__name__}")
        # Verificar métodos críticos
        if hasattr(admin_class, 'save_model'):
            print("✅ save_model existe")
        if hasattr(admin_class, 'save_formset'):
            print("✅ save_formset existe")
        if hasattr(admin_class, 'get_form'):
            print("✅ get_form existe")
    else:
        print("❌ ComandaAdmin NO está registrado")
except Exception as e:
    print(f"❌ Error verificando admin: {e}")

# 2. Verificar campos requeridos
print("\n2. Verificando campos requeridos del modelo Comanda...")
try:
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'ventas_comanda'
            AND is_nullable = 'NO'
            AND column_default IS NULL
            ORDER BY ordinal_position
        """)
        required_fields = cursor.fetchall()
        if required_fields:
            print("Campos obligatorios sin valor por defecto:")
            for field in required_fields:
                print(f"   - {field[0]}")
        else:
            print("✅ No hay campos problemáticos")
except Exception as e:
    print(f"❌ Error verificando campos: {e}")

# 3. Intentar crear una comanda programáticamente
print("\n3. Probando crear comanda programáticamente...")
try:
    # Buscar datos necesarios
    vr = VentaReserva.objects.filter(id=4965).first()
    if not vr:
        vr = VentaReserva.objects.filter(estado_reserva='confirmada').first()

    producto = Producto.objects.filter(nombre__icontains='cafe').first()
    if not producto:
        producto = Producto.objects.first()

    deborah = User.objects.filter(username='Deborah').first()
    ernesto = User.objects.filter(username='Ernesto').first()

    print(f"   VentaReserva: {vr.id if vr else 'NO ENCONTRADA'}")
    print(f"   Producto: {producto.nombre if producto else 'NO ENCONTRADO'}")
    print(f"   Deborah: {'✅' if deborah else '❌'}")
    print(f"   Ernesto: {'✅' if ernesto else '❌'}")

    if vr and producto:
        # Simular lo que haría el admin
        comanda = Comanda()
        comanda.venta_reserva = vr
        comanda.estado = 'pendiente'
        comanda.usuario_solicita = deborah
        comanda.usuario_procesa = ernesto
        comanda._from_admin = True
        comanda._is_new_from_admin = True

        print("\n   Intentando guardar comanda...")
        comanda.save()
        print(f"   ✅ Comanda guardada con ID: {comanda.id}")

        # Ahora el detalle
        detalle = DetalleComanda()
        detalle.comanda = comanda
        detalle.producto = producto
        detalle.cantidad = 2
        detalle.especificaciones = "Test desde debug"

        print("   Intentando guardar detalle...")
        detalle.save()
        print(f"   ✅ Detalle guardado. Precio: ${detalle.precio_unitario}")

except Exception as e:
    print(f"   ❌ Error: {type(e).__name__}: {str(e)}")
    traceback.print_exc()

# 4. Verificar permisos
print("\n4. Verificando permisos de usuarios...")
try:
    for username in ['Deborah', 'Ernesto']:
        user = User.objects.filter(username=username).first()
        if user:
            is_staff = user.is_staff
            is_active = user.is_active
            perms = user.get_all_permissions()
            comanda_perms = [p for p in perms if 'comanda' in p.lower()]
            print(f"   {username}: staff={is_staff}, active={is_active}, permisos_comanda={len(comanda_perms)}")
except Exception as e:
    print(f"❌ Error verificando permisos: {e}")

print("\n=== FIN DEL DEBUG ===")