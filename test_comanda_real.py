import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Comanda, VentaReserva
from django.contrib.auth.models import User

print("=== TEST CREAR COMANDA ===\n")

try:
    # Buscar una VentaReserva existente
    vr = VentaReserva.objects.filter(estado_reserva='confirmado').first()
    if not vr:
        vr = VentaReserva.objects.first()

    if not vr:
        print("❌ No hay VentaReserva en la base de datos")
        exit(1)

    print(f"✅ VentaReserva encontrada: ID={vr.id}, Cliente={vr.cliente}")

    # Buscar usuario
    user = User.objects.filter(is_staff=True).first()
    if not user:
        print("❌ No hay usuarios staff")
        exit(1)

    print(f"✅ Usuario encontrado: {user.username}")

    # Intentar crear comanda
    print("\nCreando comanda...")
    c = Comanda.objects.create(
        venta_reserva=vr,
        notas_generales='Test desde script',
        estado='pendiente',
        usuario_solicita=user,
        usuario_procesa=user
    )

    print(f"✅ Comanda creada exitosamente!")
    print(f"   - ID: {c.id}")
    print(f"   - fecha_solicitud: {c.fecha_solicitud}")
    print(f"   - hora_solicitud: {c.hora_solicitud}")

    # Limpiar
    c.delete()
    print("✅ Comanda eliminada")

except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()