#!/usr/bin/env python
"""
Debug por qué el slot bloqueado no se refleja en la disponibilidad
"""
import os
import django
from datetime import date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioSlotBloqueo, Servicio
from ventas.views.availability_views import is_slot_available

print("=== DEBUG DISPONIBILIDAD SLOT ===\n")

# 1. Obtener Tina Calbuco
tina_calbuco = Servicio.objects.filter(nombre__icontains='Calbuco').first()
fecha_test = date(2026, 3, 26)
hora_test = '19:30'

if not tina_calbuco:
    print("❌ No se encontró Tina Calbuco")
    exit(1)

print(f"1. Servicio: {tina_calbuco.nombre} (ID: {tina_calbuco.id})")
print(f"   Fecha: {fecha_test}")
print(f"   Hora: {hora_test}")

# 2. Verificar si hay bloqueo en BD
print("\n2. Verificando en base de datos...")
bloqueos = ServicioSlotBloqueo.objects.filter(
    servicio=tina_calbuco,
    fecha=fecha_test,
    activo=True
)
print(f"   Total bloqueos activos para esta fecha: {bloqueos.count()}")
for b in bloqueos:
    print(f"   - Hora: {b.hora_slot}, Motivo: {b.motivo}")

# 3. Probar método slot_bloqueado
print("\n3. Probando ServicioSlotBloqueo.slot_bloqueado()...")
esta_bloqueado = ServicioSlotBloqueo.slot_bloqueado(
    tina_calbuco.id,
    fecha_test,
    hora_test
)
print(f"   Resultado: {esta_bloqueado}")

# 4. Probar is_slot_available
print("\n4. Probando is_slot_available()...")
try:
    disponible = is_slot_available(
        tina_calbuco,
        fecha_test,
        hora_test
    )
    print(f"   ¿Está disponible?: {disponible}")
    if disponible and esta_bloqueado:
        print("   ❌ ERROR: El slot está bloqueado pero se muestra como disponible")
except Exception as e:
    print(f"   Error: {e}")
    import traceback
    traceback.print_exc()

# 5. Verificar categoría y visibilidad
print("\n5. Verificando configuración del servicio...")
print(f"   Categoría: {tina_calbuco.categoria}")
print(f"   Visible en matriz: {tina_calbuco.visible_en_matriz}")
print(f"   Activo: {tina_calbuco.activo}")

# 6. Debug: Ver qué horarios tiene configurados
print("\n6. Slots configurados para esta fecha:")
try:
    from ventas.views.calendario_matriz_view import extraer_slots_para_fecha
    slots_config = extraer_slots_para_fecha(
        tina_calbuco.slots_disponibles,
        fecha_test
    )
    print(f"   Slots disponibles: {slots_config}")

    if hora_test not in slots_config:
        print(f"   ⚠️ ADVERTENCIA: {hora_test} no está en la configuración de slots")
except Exception as e:
    print(f"   No se pudo extraer slots: {e}")

print("\n=== FIN DEBUG ===")