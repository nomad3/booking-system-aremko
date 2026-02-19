import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio, ServicioSlotBloqueo

print("=== VERIFICAR MASAJES ===")

# Ver servicios de masaje
masajes = Servicio.objects.filter(nombre__icontains='masaje')
print(f"\nServicios de masaje: {masajes.count()}")
for m in masajes[:3]:
    print(f"- {m.nombre} (ID: {m.id}, Tipo: {m.tipo_servicio})")

# Ver si hay bloqueos para masajes
for m in masajes[:1]:
    bloqueos = ServicioSlotBloqueo.objects.filter(servicio=m)
    print(f"\nBloqueos para {m.nombre}: {bloqueos.count()}")

# Verificar modelo
fields = [f.name for f in ServicioSlotBloqueo._meta.get_fields()]
print(f"\nCampos en ServicioSlotBloqueo: {fields}")
print(f"¿Tiene notas? {'SI' if 'notas' in fields else 'NO'}")