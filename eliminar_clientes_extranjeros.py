"""
Script para eliminar clientes extranjeros y con teléfonos sospechosos
de la base de datos de servicios históricos.

IMPORTANTE: Este script ELIMINA datos permanentemente.
- Elimina 39 clientes
- Elimina 1,168 servicios históricos asociados
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ServiceHistory
from django.db import transaction

print("\n" + "="*100)
print("SCRIPT DE ELIMINACION DE CLIENTES EXTRANJEROS Y SOSPECHOSOS")
print("="*100 + "\n")

# IDs a eliminar
FORMATOS_RAROS = [137, 148, 133, 131, 169, 3561, 136]  # 7 clientes

SOSPECHOSOS = [994, 4606, 574, 1191, 713, 536, 1150, 530]  # 8 clientes

ARGENTINOS = [1075, 3798, 1044]  # 3 clientes

EXTRANJEROS = [
    944, 1171, 1274, 774, 1109, 1161, 620, 306, 662, 607,
    999, 987, 458, 1168, 520, 398, 1020, 454, 1013, 984, 798
]  # 21 clientes

TODOS_LOS_IDS = FORMATOS_RAROS + SOSPECHOSOS + ARGENTINOS + EXTRANJEROS

print(f"Total de clientes a eliminar: {len(TODOS_LOS_IDS)}")
print(f"  - Formatos raros:     {len(FORMATOS_RAROS)}")
print(f"  - Sospechosos:        {len(SOSPECHOSOS)}")
print(f"  - Argentinos:         {len(ARGENTINOS)}")
print(f"  - Otros extranjeros:  {len(EXTRANJEROS)}")

# PASO 1: Verificar que existen y contar servicios
print("\n" + "="*100)
print("PASO 1: VERIFICANDO CLIENTES Y SERVICIOS")
print("="*100 + "\n")

clientes_a_eliminar = []
total_servicios = 0

for cliente_id in TODOS_LOS_IDS:
    try:
        cliente = Cliente.objects.get(id=cliente_id)
        num_servicios = ServiceHistory.objects.filter(cliente=cliente).count()
        total_servicios += num_servicios

        clientes_a_eliminar.append({
            'id': cliente.id,
            'nombre': cliente.nombre,
            'telefono': cliente.telefono,
            'num_servicios': num_servicios
        })

        print(f"✓ ID {cliente.id:<5} - {cliente.nombre:<40} - {cliente.telefono:<20} - {num_servicios:>4} servicios")
    except Cliente.DoesNotExist:
        print(f"✗ ID {cliente_id} NO ENCONTRADO")

print(f"\n{'='*100}")
print(f"RESUMEN:")
print(f"  Clientes encontrados:     {len(clientes_a_eliminar)}")
print(f"  Servicios a eliminar:     {total_servicios:,}")
print(f"{'='*100}\n")

# CONFIRMACION
print("⚠️  ADVERTENCIA: Esta operación NO SE PUEDE DESHACER\n")
confirmacion = input("¿Estás seguro de eliminar estos datos? Escribe 'SI ELIMINAR' para confirmar: ")

if confirmacion != "SI ELIMINAR":
    print("\n❌ OPERACION CANCELADA - No se eliminó nada")
    exit(0)

print("\n✓ Confirmación recibida. Procediendo con eliminación...\n")

# PASO 2: ELIMINAR
print("="*100)
print("PASO 2: ELIMINANDO DATOS")
print("="*100 + "\n")

log_file = f"eliminacion_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

with open(log_file, 'w') as log:
    log.write("="*100 + "\n")
    log.write(f"LOG DE ELIMINACION - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write("="*100 + "\n\n")

    clientes_eliminados = 0
    servicios_eliminados = 0

    with transaction.atomic():
        for info in clientes_a_eliminar:
            try:
                cliente = Cliente.objects.get(id=info['id'])

                # Eliminar servicios históricos primero
                servicios_del_cliente = ServiceHistory.objects.filter(cliente=cliente)
                num_servicios = servicios_del_cliente.count()
                servicios_del_cliente.delete()

                # Eliminar cliente
                cliente.delete()

                clientes_eliminados += 1
                servicios_eliminados += num_servicios

                mensaje = f"✓ Eliminado: ID {info['id']} - {info['nombre']} - {num_servicios} servicios"
                print(mensaje)
                log.write(mensaje + "\n")

            except Exception as e:
                mensaje = f"✗ ERROR al eliminar ID {info['id']}: {str(e)}"
                print(mensaje)
                log.write(mensaje + "\n")

    log.write(f"\n{'='*100}\n")
    log.write(f"RESUMEN FINAL:\n")
    log.write(f"  Clientes eliminados:      {clientes_eliminados}\n")
    log.write(f"  Servicios eliminados:     {servicios_eliminados:,}\n")
    log.write(f"{'='*100}\n")

print(f"\n{'='*100}")
print("RESULTADO FINAL:")
print("="*100)
print(f"✓ Clientes eliminados:      {clientes_eliminados}")
print(f"✓ Servicios eliminados:     {servicios_eliminados:,}")
print(f"\nLog guardado en: {log_file}")
print("="*100 + "\n")

print("✅ OPERACION COMPLETADA EXITOSAMENTE\n")
