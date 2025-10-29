"""
Script para eliminar los 4 clientes duplicados sin + en el teléfono
Estos son duplicados de otros clientes que ya tienen el formato correcto
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ServiceHistory
from django.db import transaction

DUPLICADOS_A_ELIMINAR = [4323, 4035, 3712, 3754]

print("\n" + "="*80)
print("ELIMINANDO 4 DUPLICADOS SIN + EN TELEFONO")
print("="*80 + "\n")

print("Estos son duplicados de:")
print("  ID 4323 (56292759319)  → Duplicado de ID 113 (+56292759319)")
print("  ID 4035 (56946891194)  → Duplicado de ID 753 (+56946891194)")
print("  ID 3712 (56299186035)  → Duplicado de ID 186 (+56299186035)")
print("  ID 3754 (56298704718)  → Duplicado de ID 652 (+56298704718)")
print()

with transaction.atomic():
    eliminados = 0
    servicios_eliminados = 0

    for cliente_id in DUPLICADOS_A_ELIMINAR:
        try:
            cliente = Cliente.objects.get(id=cliente_id)
            num_servicios = ServiceHistory.objects.filter(cliente=cliente).count()

            print(f"Eliminando ID {cliente.id:<5} - {cliente.nombre:<40} - Tel: {cliente.telefono:<15} - {num_servicios} servicios")

            # Eliminar servicios históricos
            ServiceHistory.objects.filter(cliente=cliente).delete()

            # Eliminar cliente
            cliente.delete()

            eliminados += 1
            servicios_eliminados += num_servicios

        except Cliente.DoesNotExist:
            print(f"✗ ID {cliente_id} no encontrado")

print(f"\n" + "="*80)
print(f"RESULTADO:")
print(f"  ✓ Clientes eliminados:    {eliminados}")
print(f"  ✓ Servicios eliminados:   {servicios_eliminados}")
print("="*80 + "\n")

print("✅ OPERACION COMPLETADA\n")
