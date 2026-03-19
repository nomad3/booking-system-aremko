#!/usr/bin/env python
"""
Script simple para probar el método slot_bloqueado directamente
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioSlotBloqueo, Servicio
from datetime import date

print("=== TEST MÉTODO slot_bloqueado ===\n")

# 1. Obtener un slot bloqueado activo
slot = ServicioSlotBloqueo.objects.filter(activo=True).first()

if slot:
    print(f"1. Probando con slot bloqueado existente:")
    print(f"   Servicio: {slot.servicio.nombre} (ID: {slot.servicio.id})")
    print(f"   Fecha: {slot.fecha}")
    print(f"   Hora: {slot.hora_slot}")
    print(f"   Activo: {slot.activo}")

    # 2. Probar el método
    print("\n2. Llamando ServicioSlotBloqueo.slot_bloqueado()...")
    try:
        resultado = ServicioSlotBloqueo.slot_bloqueado(
            slot.servicio.id,
            slot.fecha,
            slot.hora_slot
        )
        print(f"   Resultado: {resultado}")
        print(f"   {'✅ CORRECTO' if resultado else '❌ ERROR'} - Debería ser True")
    except Exception as e:
        print(f"   ❌ ERROR al llamar método: {e}")
        import traceback
        traceback.print_exc()

    # 3. Probar con un slot no bloqueado
    print("\n3. Probando con slot NO bloqueado (hora diferente)...")
    hora_diferente = "23:59" if slot.hora_slot != "23:59" else "00:00"
    try:
        resultado = ServicioSlotBloqueo.slot_bloqueado(
            slot.servicio.id,
            slot.fecha,
            hora_diferente
        )
        print(f"   Resultado: {resultado}")
        print(f"   {'✅ CORRECTO' if not resultado else '❌ ERROR'} - Debería ser False")
    except Exception as e:
        print(f"   ❌ ERROR al llamar método: {e}")
        import traceback
        traceback.print_exc()
else:
    print("❌ No hay slots bloqueados activos para probar")
    print("\nCreando un slot bloqueado de prueba...")

    servicio = Servicio.objects.filter(activo=True).first()
    if servicio:
        slot = ServicioSlotBloqueo.objects.create(
            servicio=servicio,
            fecha=date.today(),
            hora_slot="14:00",
            motivo="Prueba del método",
            activo=True
        )
        print(f"✅ Creado slot de prueba: {slot}")

        # Probar
        resultado = ServicioSlotBloqueo.slot_bloqueado(
            servicio.id,
            date.today(),
            "14:00"
        )
        print(f"\nProbando método: {resultado}")
        print(f"{'✅ FUNCIONA' if resultado else '❌ NO FUNCIONA'}")

        # Limpiar
        slot.delete()
        print("\n✅ Slot de prueba eliminado")

print("\n=== FIN TEST ===")