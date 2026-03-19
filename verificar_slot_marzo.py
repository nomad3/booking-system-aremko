#!/usr/bin/env python
"""
Verificar si el slot bloqueado de marzo se guardó correctamente
"""
import os
import django
from datetime import datetime, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServicioSlotBloqueo, Servicio

print("=== VERIFICACIÓN SLOT MARZO ===\n")

# 1. Buscar slots bloqueados para marzo 2026
print("1. Buscando slots bloqueados en marzo 2026...")
fecha_buscar = date(2026, 3, 26)
slots_marzo = ServicioSlotBloqueo.objects.filter(
    fecha__year=2026,
    fecha__month=3
).order_by('-created_at')

print(f"   Total encontrados: {slots_marzo.count()}")

for slot in slots_marzo[:10]:
    print(f"\n   ID: {slot.id}")
    print(f"   Servicio: {slot.servicio.nombre}")
    print(f"   Fecha: {slot.fecha}")
    print(f"   Hora: {slot.hora_slot}")
    print(f"   Activo: {slot.activo}")
    print(f"   Creado: {slot.created_at}")

# 2. Buscar específicamente Tina Calbuco
print("\n2. Buscando Tina Calbuco 26/03/2026 19:30...")
tina_calbuco = Servicio.objects.filter(nombre__icontains='Calbuco').first()

if tina_calbuco:
    print(f"   Servicio encontrado: {tina_calbuco.nombre} (ID: {tina_calbuco.id})")

    slot_especifico = ServicioSlotBloqueo.objects.filter(
        servicio=tina_calbuco,
        fecha=fecha_buscar,
        hora_slot='19:30'
    ).first()

    if slot_especifico:
        print(f"   ✅ SLOT ENCONTRADO:")
        print(f"      ID: {slot_especifico.id}")
        print(f"      Activo: {slot_especifico.activo}")
        print(f"      Motivo: {slot_especifico.motivo}")

        # Probar el método
        bloqueado = ServicioSlotBloqueo.slot_bloqueado(
            tina_calbuco.id,
            fecha_buscar,
            '19:30'
        )
        print(f"\n   Test slot_bloqueado(): {bloqueado}")
    else:
        print(f"   ❌ NO se encontró el slot bloqueado")

# 3. Ver últimos 5 slots creados
print("\n3. Últimos 5 slots bloqueados creados:")
ultimos = ServicioSlotBloqueo.objects.all().order_by('-created_at')[:5]
for slot in ultimos:
    print(f"   - {slot.servicio.nombre} | {slot.fecha} {slot.hora_slot} | Activo: {slot.activo}")

print("\n=== FIN VERIFICACIÓN ===")