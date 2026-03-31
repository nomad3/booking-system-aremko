#!/usr/bin/env python
"""
Script para probar la API de disponibilidad de Tina Calbuco
Ejecutar: python scripts/test_calbuco_api.py
"""

import os
import sys
import django
from datetime import datetime, timedelta

# Setup Django
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
print("PRUEBA DE API - TINA CALBUCO")
print("="*60)

# Datos de Tina Calbuco
servicio_id = 12
tomorrow = datetime.now().date() + timedelta(days=1)
day_name = tomorrow.strftime('%A').lower()

print(f"\nServicio ID: {servicio_id}")
print(f"Fecha: {tomorrow} ({day_name})")

# Obtener el servicio
try:
    servicio = Servicio.objects.get(id=servicio_id)
    print(f"Servicio: {servicio.nombre}")
    print(f"Activo: {servicio.activo}")
    print(f"Max simultáneos: {getattr(servicio, 'max_servicios_simultaneos', 1)}")
except Servicio.DoesNotExist:
    print("❌ Servicio no encontrado")
    sys.exit(1)

# 1. Verificar si el servicio está bloqueado por día completo
print("\n" + "-"*60)
print("1. VERIFICACIÓN DE BLOQUEOS DE DÍA COMPLETO")
print("-"*60)

if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, tomorrow):
    print(f"❌ El servicio está BLOQUEADO para {tomorrow}")
    sys.exit(0)
else:
    print(f"✅ No hay bloqueo de día completo")

# 2. Obtener slots configurados
print("\n" + "-"*60)
print("2. SLOTS CONFIGURADOS EN BASE DE DATOS")
print("-"*60)

if isinstance(servicio.slots_disponibles, dict):
    slots_configurados = servicio.slots_disponibles.get(day_name, [])
    print(f"Slots configurados para {day_name}: {len(slots_configurados)}")
    if slots_configurados:
        print(f"Horarios: {slots_configurados}")
    else:
        print(f"⚠️  NO hay slots configurados para {day_name}")
        print(f"Días disponibles: {list(servicio.slots_disponibles.keys())}")
        sys.exit(0)
else:
    print(f"❌ slots_disponibles no es un diccionario: {type(servicio.slots_disponibles)}")
    sys.exit(1)

# 3. Verificar reservas existentes
print("\n" + "-"*60)
print("3. RESERVAS EXISTENTES")
print("-"*60)

reservas_por_hora = ReservaServicio.objects.filter(
    servicio=servicio,
    fecha_agendamiento=tomorrow
).exclude(
    venta_reserva__estado_reserva='cancelada'
).values('hora_inicio').annotate(cantidad=Count('id'))

slots_ocupacion = {str(r['hora_inicio']): r['cantidad'] for r in reservas_por_hora}

if slots_ocupacion:
    print("Slots ocupados:")
    for hora, cantidad in slots_ocupacion.items():
        print(f"  {hora}: {cantidad} reserva(s)")
else:
    print("✅ No hay reservas para mañana")

# 4. Verificar bloqueos de slots individuales
print("\n" + "-"*60)
print("4. BLOQUEOS DE SLOTS INDIVIDUALES")
print("-"*60)

bloqueos_slot = ServicioSlotBloqueo.objects.filter(
    servicio=servicio,
    fecha=tomorrow,
    activo=True
).values_list('hora_slot', flat=True)

slots_bloqueados_set = set(bloqueos_slot)

if slots_bloqueados_set:
    print(f"Slots bloqueados: {slots_bloqueados_set}")
else:
    print("✅ No hay slots bloqueados individualmente")

# 5. Calcular slots disponibles (igual que hace la API)
print("\n" + "-"*60)
print("5. CÁLCULO DE DISPONIBILIDAD (SIMULACIÓN DE API)")
print("-"*60)

max_simultaneos = getattr(servicio, 'max_servicios_simultaneos', 1)
print(f"Capacidad máxima por slot: {max_simultaneos}")

horas_disponibles = []
for hora in slots_configurados:
    hora_str = str(hora)

    # Verificar si está bloqueado
    if hora_str in slots_bloqueados_set:
        print(f"  {hora_str}: BLOQUEADO (slot individual)")
        continue

    # Verificar capacidad
    reservas_existentes = slots_ocupacion.get(hora_str, 0)
    if reservas_existentes < max_simultaneos:
        horas_disponibles.append(hora_str)
        print(f"  {hora_str}: DISPONIBLE ({reservas_existentes}/{max_simultaneos} ocupados)")
    else:
        print(f"  {hora_str}: LLENO ({reservas_existentes}/{max_simultaneos} ocupados)")

# 6. Resultado final
print("\n" + "="*60)
print("RESULTADO FINAL")
print("="*60)

print(f"\n✅ Slots disponibles para {tomorrow}: {len(horas_disponibles)}")
if horas_disponibles:
    print(f"Horarios disponibles: {horas_disponibles}")
else:
    print("⚠️  NO HAY SLOTS DISPONIBLES")
    print("\nPosibles causas:")
    if not slots_configurados:
        print(f"  - No hay slots configurados para {day_name}")
    if slots_bloqueados_set:
        print(f"  - Todos los slots están bloqueados individualmente")
    if slots_ocupacion:
        print(f"  - Todos los slots están completamente reservados")

print(f"\nURL de prueba:")
print(f"curl 'https://aremko.cl/ventas/get-available-hours/?servicio_id={servicio_id}&fecha={tomorrow}'")

print("\n" + "="*60)