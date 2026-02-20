import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Comanda, VentaReserva
from django.contrib.auth.models import User

print("=== TEST CREAR COMANDA CON ID 39 ===\n")

try:
    # Usar VentaReserva ID 39
    vr = VentaReserva.objects.get(id=39)
    print(f"✅ VentaReserva encontrada: ID={vr.id}, Cliente={vr.cliente}")

    # Usar usuario Ernesto (ID 7)
    user = User.objects.get(id=7)
    print(f"✅ Usuario encontrado: {user.username}")

    # Crear comanda
    print("\nCreando comanda...")
    c = Comanda(
        venta_reserva=vr,
        notas_generales='Test desde script - ID 39',
        estado='pendiente',
        usuario_solicita=user,
        usuario_procesa=user
    )

    # Marcar que NO viene del admin
    c._from_admin = False

    # Guardar
    c.save()

    print(f"✅ Comanda creada exitosamente!")
    print(f"   - ID: {c.id}")
    print(f"   - fecha_solicitud: {c.fecha_solicitud}")
    print(f"   - hora_solicitud: {c.hora_solicitud}")
    print(f"   - venta_reserva: {c.venta_reserva_id}")
    print(f"   - usuario_solicita: {c.usuario_solicita.username}")

    # Verificar que se guardó
    c_verificada = Comanda.objects.get(id=c.id)
    print(f"\n✅ Comanda verificada en BD: ID={c_verificada.id}")

    # Limpiar
    c.delete()
    print("✅ Comanda eliminada")

except Exception as e:
    print(f"\n❌ Error: {type(e).__name__}: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN DEL TEST ===")