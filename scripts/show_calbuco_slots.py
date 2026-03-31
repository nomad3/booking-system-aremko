#!/usr/bin/env python
"""
Script para mostrar todos los slots de Tina Calbuco
Ejecutar: python scripts/show_calbuco_slots.py
"""

import os
import sys
import django

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

from ventas.models import Servicio

print("\n" + "="*60)
print("CONFIGURACIÓN DE SLOTS - TINA CALBUCO")
print("="*60)

calbuco = Servicio.objects.get(id=12)

print(f"\nServicio: {calbuco.nombre} (ID: {calbuco.id})")
print(f"\nSlots por día de la semana:")
print("-" * 40)

dias_ordenados = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']

if isinstance(calbuco.slots_disponibles, dict):
    for dia in dias_ordenados:
        slots = calbuco.slots_disponibles.get(dia, [])
        if slots:
            print(f"\n{dia.upper():12s}: {len(slots)} slots")
            for slot in slots:
                print(f"               {slot}")
        else:
            print(f"\n{dia.upper():12s}: ❌ SIN SLOTS CONFIGURADOS")

    # Análisis
    print("\n" + "="*60)
    print("ANÁLISIS")
    print("="*60)

    dias_con_slots = [dia for dia in dias_ordenados if calbuco.slots_disponibles.get(dia)]
    dias_sin_slots = [dia for dia in dias_ordenados if not calbuco.slots_disponibles.get(dia)]

    print(f"\nDías con slots configurados: {len(dias_con_slots)}")
    for dia in dias_con_slots:
        print(f"  ✅ {dia}: {len(calbuco.slots_disponibles[dia])} slots")

    if dias_sin_slots:
        print(f"\nDías SIN slots configurados: {len(dias_sin_slots)}")
        for dia in dias_sin_slots:
            print(f"  ❌ {dia}")

        print("\n" + "-"*60)
        print("💡 RECOMENDACIÓN:")
        print("-"*60)
        print("\nPara que todos los días tengan disponibilidad,")
        print("necesitas configurar slots para los días faltantes.")
        print("\nEjemplo de horarios comunes:")
        print("  ['09:00', '11:00', '14:00', '17:00']")
else:
    print("❌ slots_disponibles no es un diccionario")

print("\n" + "="*60)