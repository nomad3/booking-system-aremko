import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import VentaReserva, Comanda
from django.contrib.auth.models import User

print("=== VERIFICAR DATOS ===\n")

# Verificar VentaReserva
print("1. VentaReserva disponibles:")
vrs = VentaReserva.objects.all()[:5]
if vrs:
    for vr in vrs:
        print(f"   - ID={vr.id}, Cliente={vr.cliente}, Estado={vr.estado}")
else:
    print("   ❌ No hay VentaReserva")

# Verificar usuarios
print("\n2. Usuarios staff:")
users = User.objects.filter(is_staff=True)[:5]
for u in users:
    print(f"   - {u.username} (ID={u.id})")

# Verificar comandas existentes
print("\n3. Comandas existentes:")
comandas = Comanda.objects.all()[:5]
if comandas:
    for c in comandas:
        print(f"   - ID={c.id}, VentaReserva={c.venta_reserva_id}, Estado={c.estado}")
else:
    print("   No hay comandas")

print("\n=== FIN ===")