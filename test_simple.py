import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import VentaReserva
from django.contrib.auth.models import User

print("=== DATOS DISPONIBLES ===\n")

# Ver VentaReservas
print("VentaReserva (primeras 5):")
for vr in VentaReserva.objects.all()[:5]:
    print(f"  ID={vr.id}, Cliente={getattr(vr.cliente, 'nombre', 'Sin cliente')}")

# Ver usuarios
print("\nUsuarios staff:")
for u in User.objects.filter(is_staff=True)[:5]:
    print(f"  {u.username} (ID={u.id})")