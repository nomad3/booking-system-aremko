#!/usr/bin/env python
"""
Script para probar disponibilidad de Tina Calbuco para miércoles
Ejecutar: python scripts/test_wednesday_availability.py
"""

import os
import sys
import django
from datetime import datetime, timedelta

sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

try:
    django.setup()
except Exception:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings')
    try:
        django.setup()
    except Exception:
        for possible_name in ['aremko_project.settings', 'config.settings', 'mysite.settings']:
            try:
                os.environ['DJANGO_SETTINGS_MODULE'] = possible_name
                django.setup()
                break
            except:
                continue

from ventas.models import Servicio, ReservaServicio, ServicioBloqueo, ServicioSlotBloqueo
from django.db.models import Count

print("\n" + "="*60)
print("PRUEBA DE DISPONIBILIDAD - MIÉRCOLES")
print("="*60)

# Encontrar el próximo miércoles
hoy = datetime.now().date()
dias_hasta_miercoles = (2 - hoy.weekday()) % 7  # 2 = miércoles
if dias_hasta_miercoles == 0:
    dias_hasta_miercoles = 7  # Si hoy es miércoles, buscar el próximo

wednesday = hoy + timedelta(days=dias_hasta_miercoles)

servicio_id = 12
day_name = 'wednesday'

print(f"\nFecha de prueba: {wednesday} (miércoles)")
print(f"Servicio ID: {servicio_id} (Tina Calbuco)")

# Obtener el servicio
servicio = Servicio.objects.get(id=servicio_id)

# 1. Verificar bloqueos de día completo
print("\n" + "-"*60)
print("1. BLOQUEOS DE DÍA COMPLETO")
print("-"*60)

if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, wednesday):
    print(f"❌ BLOQUEADO para {wednesday}")
    sys.exit(0)
else:
    print(f"✅ No hay bloqueo de día completo")

# 2. Slots configurados
print("\n" + "-"*60)
print("2. SLOTS CONFIGURADOS")
print("-"*60)

slots_configurados = servicio.slots_disponibles.get(day_name, [])
print(f"Slots para {day_name}: {len(slots_configurados)}")
if slots_configurados:
    print(f"Horarios: {slots_configurados}")
else:
    print("❌ NO hay slots configurados")
    sys.exit(0)

# 3. Reservas existentes
print("\n" + "-"*60)
print("3. RESERVAS EXISTENTES")
print("-"*60)

reservas_por_hora = ReservaServicio.objects.filter(
    servicio=servicio,
    fecha_agendamiento=wednesday
).exclude(
    venta_reserva__estado_reserva='cancelada'
).values('hora_inicio').annotate(cantidad=Count('id'))

slots_ocupacion = {str(r['hora_inicio']): r['cantidad'] for r in reservas_por_hora}

if slots_ocupacion:
    print("Slots con reservas:")
    for hora, cantidad in slots_ocupacion.items():
        print(f"  {hora}: {cantidad} reserva(s)")
else:
    print("✅ No hay reservas")

# 4. Bloqueos individuales
print("\n" + "-"*60)
print("4. BLOQUEOS INDIVIDUALES DE SLOTS")
print("-"*60)

bloqueos_slot = ServicioSlotBloqueo.objects.filter(
    servicio=servicio,
    fecha=wednesday,
    activo=True
).values_list('hora_slot', flat=True)

slots_bloqueados_set = set(bloqueos_slot)

if slots_bloqueados_set:
    print(f"Slots bloqueados: {slots_bloqueados_set}")
else:
    print("✅ No hay bloqueos individuales")

# 5. Cálculo final
print("\n" + "-"*60)
print("5. DISPONIBILIDAD FINAL")
print("-"*60)

max_simultaneos = getattr(servicio, 'max_servicios_simultaneos', 1)

horas_disponibles = []
for hora in slots_configurados:
    hora_str = str(hora)

    if hora_str in slots_bloqueados_set:
        print(f"  {hora_str}: BLOQUEADO")
        continue

    reservas_existentes = slots_ocupacion.get(hora_str, 0)
    if reservas_existentes < max_simultaneos:
        horas_disponibles.append(hora_str)
        print(f"  {hora_str}: ✅ DISPONIBLE")
    else:
        print(f"  {hora_str}: LLENO")

print("\n" + "="*60)
print("RESULTADO")
print("="*60)

print(f"\n📅 Fecha: {wednesday} (miércoles)")
print(f"🎯 Tina Calbuco (ID: {servicio_id})")
print(f"✅ Slots disponibles: {len(horas_disponibles)}")

if horas_disponibles:
    print(f"\nHorarios disponibles:")
    for hora in horas_disponibles:
        print(f"  • {hora}")
else:
    print("\n⚠️  NO HAY DISPONIBILIDAD")

# URLs de prueba
print("\n" + "-"*60)
print("PRUEBAS DE API")
print("-"*60)

print(f"\n1. API antigua (ventas):")
print(f"curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id={servicio_id}&fecha={wednesday}'")

print(f"\n2. API nueva (con autenticación):")
print(f"curl -H 'X-API-Key: wmRL0kJ52oq15VfTW8db0bZuYYHLoKKq3mXzwGXXnms' \\")
print(f"     'https://aremko.cl/api/v1/availability/tinajas/?date={wednesday}'")

print("\n" + "="*60)