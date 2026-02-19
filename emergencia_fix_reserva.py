#!/usr/bin/env python
"""
Script de EMERGENCIA para diagnosticar y reparar el error en la reserva
Ejecutar con: python manage.py shell < emergencia_fix_reserva.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import VentaReserva, Comanda, ReservaProducto
from django.db import connection

print("\n" + "=" * 80)
print("DIAGNÓSTICO DE EMERGENCIA - RESERVA 5002")
print("=" * 80)
print()

# 1. Verificar el estado de la reserva
print("1. VERIFICANDO RESERVA 5002")
print("-" * 40)

try:
    reserva = VentaReserva.objects.get(id=5002)
    print(f"✓ Reserva encontrada")
    print(f"  Cliente: {reserva.cliente}")
    print(f"  Estado: {reserva.estado_reserva}")
    print(f"  Total: ${reserva.total}")
except Exception as e:
    print(f"✗ Error al cargar reserva: {e}")

# 2. Verificar comandas recientes
print("\n2. VERIFICANDO COMANDAS RECIENTES")
print("-" * 40)

comandas_recientes = Comanda.objects.filter(
    venta_reserva_id=5002
).order_by('-id')[:5]

if comandas_recientes:
    print(f"Comandas encontradas: {comandas_recientes.count()}")
    for comanda in comandas_recientes:
        print(f"\n  Comanda ID: {comanda.id}")
        print(f"  Estado: {comanda.estado}")
        print(f"  Creada: {comanda.fecha_solicitud}")
        print(f"  Detalles: {comanda.detalles.count()}")

        # Verificar si tiene problemas
        try:
            total = comanda.total_items
            print(f"  Total items: {total}")
        except Exception as e:
            print(f"  ✗ Error al calcular total: {e}")

# 3. Buscar posibles datos corruptos
print("\n3. VERIFICANDO INTEGRIDAD DE DATOS")
print("-" * 40)

with connection.cursor() as cursor:
    # Verificar comandas sin detalles
    cursor.execute("""
        SELECT c.id, c.fecha_solicitud
        FROM ventas_comanda c
        LEFT JOIN ventas_detallecomanda d ON c.id = d.comanda_id
        WHERE c.venta_reserva_id = 5002
        AND d.id IS NULL
    """)

    comandas_sin_detalles = cursor.fetchall()
    if comandas_sin_detalles:
        print(f"✗ Comandas sin detalles encontradas:")
        for cmd in comandas_sin_detalles:
            print(f"  - Comanda ID: {cmd[0]}, Fecha: {cmd[1]}")

# 4. Verificar el inline de comandas
print("\n4. POSIBLE CAUSA DEL ERROR")
print("-" * 40)

print("El error puede deberse a:")
print("1. El método validar_stock_completo accede a formset.cleaned_data")
print("2. El formset podría no estar completamente inicializado")
print("3. Algún campo calculado está causando problemas")

# 5. Solución temporal
print("\n5. SOLUCIÓN TEMPORAL")
print("-" * 40)

print("Opciones:")
print("1. Eliminar las comandas problemáticas")
print("2. Revertir el cambio en admin.py")
print("3. Aplicar un parche más seguro")

# 6. Limpiar comandas problemáticas (comentado por seguridad)
print("\nPara limpiar comandas sin detalles, ejecuta:")
print(">>> Comanda.objects.filter(venta_reserva_id=5002, detalles__isnull=True).delete()")

print("\n" + "=" * 80)
print("FIN DEL DIAGNÓSTICO")
print("=" * 80)