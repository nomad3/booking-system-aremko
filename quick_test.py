import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Comanda, VentaReserva
from django.contrib.auth.models import User

# Test rápido
try:
    vr = VentaReserva.objects.get(id=4971)
    user = User.objects.get(username='Deborah')

    # Crear comanda mínima
    c = Comanda.objects.create(
        venta_reserva=vr,
        notas_generales='Test directo',
        estado='pendiente',
        usuario_solicita=user,
        usuario_procesa=user
    )
    print(f"✅ Comanda creada: ID={c.id}")
    print(f"   fecha_solicitud: {c.fecha_solicitud}")
    print(f"   hora_solicitud: {c.hora_solicitud}")

    # Limpiar
    c.delete()
    print("✅ Comanda eliminada")

except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()