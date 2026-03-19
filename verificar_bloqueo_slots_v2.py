#!/usr/bin/env python
"""
Script para verificar por qué ServicioSlotBloqueo no está bloqueando
Versión corregida con el nombre correcto de la función
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioSlotBloqueo, Servicio
from ventas.views.availability_views import is_slot_available
from datetime import date
import importlib

print("=== VERIFICACIÓN DE BLOQUEO DE SLOTS ===\n")

# 1. Verificar si hay slots bloqueados
print("1. Slots bloqueados en la BD:")
slots_bloqueados = ServicioSlotBloqueo.objects.filter(activo=True).order_by('-id')[:5]

if not slots_bloqueados:
    print("   ❌ No hay slots bloqueados activos")
else:
    for slot in slots_bloqueados:
        print(f"   - Servicio: {slot.servicio.nombre}, Fecha: {slot.fecha}, Hora: {slot.hora_slot}")

# 2. Probar con un slot bloqueado
if slots_bloqueados:
    primer_slot = slots_bloqueados[0]
    print(f"\n2. Probando disponibilidad del primer slot bloqueado:")
    print(f"   Servicio: {primer_slot.servicio.nombre}")
    print(f"   Fecha: {primer_slot.fecha}")
    print(f"   Hora: {primer_slot.hora_slot}")

    # Verificar con el método de la clase
    print("\n3. Verificando con método ServicioSlotBloqueo.slot_bloqueado():")
    esta_bloqueado = ServicioSlotBloqueo.slot_bloqueado(
        primer_slot.servicio.id,
        primer_slot.fecha,
        primer_slot.hora_slot
    )
    print(f"   ¿Está bloqueado?: {esta_bloqueado}")

    # Verificar con is_slot_available
    print("\n4. Verificando con is_slot_available():")
    try:
        disponible = is_slot_available(
            primer_slot.servicio,
            primer_slot.fecha,
            primer_slot.hora_slot
        )
        print(f"   ¿Está disponible?: {disponible}")
        if disponible:
            print(f"   ❌ PROBLEMA: Debería ser False (no disponible)")
        else:
            print(f"   ✅ CORRECTO: El slot está bloqueado correctamente")
    except Exception as e:
        print(f"   Error al verificar: {e}")

# 3. Ver el código actual de is_slot_available
print("\n5. Revisando el código de is_slot_available:")
try:
    import inspect
    print(inspect.getsource(is_slot_available))
except Exception as e:
    print(f"   No se pudo obtener el código: {e}")

# 4. Verificar qué función se usa en el calendario
print("\n6. Verificando imports en calendario_matriz_view:")
try:
    from ventas.views import calendario_matriz_view
    # Ver si importa y usa ServicioSlotBloqueo
    codigo = inspect.getsource(calendario_matriz_view)
    if 'ServicioSlotBloqueo' in codigo:
        print("   ✅ calendario_matriz_view SÍ importa ServicioSlotBloqueo")
    else:
        print("   ❌ calendario_matriz_view NO importa ServicioSlotBloqueo")

    if 'slot_bloqueado' in codigo:
        print("   ✅ calendario_matriz_view verifica slots bloqueados")
    else:
        print("   ❌ calendario_matriz_view NO verifica slots bloqueados")
except Exception as e:
    print(f"   Error: {e}")

print("\n=== FIN VERIFICACIÓN ===")