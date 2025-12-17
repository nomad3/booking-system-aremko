#!/usr/bin/env python3
"""
Script para actualizar los slots (horarios) de las tinas según su tipo
Ejecutar: python scripts/update_tinas_slots.py
"""

import os
import sys
from pathlib import Path

# Agregar el directorio raíz del proyecto al path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')

import django
django.setup()

from ventas.models import Servicio, CategoriaServicio

print("\n" + "=" * 80)
print("ACTUALIZAR SLOTS DE TINAS")
print("=" * 80)

# Definir los slots para cada tipo de tina
SLOTS_SIN_HIDROMASAJE = ["12:00", "14:30", "17:00", "19:30", "22:00"]
SLOTS_CON_HIDROMASAJE = ["14:00", "16:30", "19:00", "21:30"]

# Tinas SIN hidromasaje
TINAS_SIN_HIDROMASAJE = [
    "Tina Hornopiren", "Tina Hornopirén",
    "Tina Tronador",
    "Tina Calbuco",
    "Tina Osorno"
]

# Tinas CON hidromasaje
TINAS_CON_HIDROMASAJE = [
    "Tina Hidromasaje Puntiagudo",
    "Tina Hidromasaje Llaima",
    "Tina Hidromasaje Villarrica",
    "Tina Hidromasaje Puyehue"
]

# Buscar la categoría de Tinas
categoria_tinas = CategoriaServicio.objects.filter(
    nombre__icontains='tina'
).exclude(
    nombre__icontains='empresarial'
).first()

if not categoria_tinas:
    print("❌ No se encontró la categoría 'Tinas Calientes'")
    sys.exit(1)

print(f"\n✅ Categoría encontrada: {categoria_tinas.nombre}")

# Actualizar tinas SIN hidromasaje
print(f"\n📋 Actualizando tinas SIN hidromasaje con slots: {SLOTS_SIN_HIDROMASAJE}")
for nombre_tina in TINAS_SIN_HIDROMASAJE:
    servicios = Servicio.objects.filter(
        nombre__icontains=nombre_tina.replace("Tina ", ""),
        categoria=categoria_tinas
    )
    for servicio in servicios:
        servicio.slots_disponibles = SLOTS_SIN_HIDROMASAJE
        servicio.save()
        print(f"   ✅ {servicio.nombre}: slots actualizados")

# Actualizar tinas CON hidromasaje
print(f"\n📋 Actualizando tinas CON hidromasaje con slots: {SLOTS_CON_HIDROMASAJE}")
for nombre_tina in TINAS_CON_HIDROMASAJE:
    # Buscar por partes del nombre
    search_term = nombre_tina.replace("Tina Hidromasaje ", "")
    servicios = Servicio.objects.filter(
        nombre__icontains=search_term,
        categoria=categoria_tinas
    )
    for servicio in servicios:
        # Verificar que realmente es una tina con hidromasaje
        if 'hidromasaje' in servicio.nombre.lower():
            servicio.slots_disponibles = SLOTS_CON_HIDROMASAJE
            servicio.save()
            print(f"   ✅ {servicio.nombre}: slots actualizados")

# Listar todos los servicios de tinas para verificar
print("\n📊 RESUMEN DE SERVICIOS DE TINAS:")
print("-" * 60)

servicios_tinas = Servicio.objects.filter(
    categoria=categoria_tinas,
    visible_en_matriz=True
).order_by('nombre')

for servicio in servicios_tinas:
    slots = servicio.slots_disponibles if servicio.slots_disponibles else []
    print(f"   • {servicio.nombre}")
    print(f"     Slots: {slots}")
    print(f"     Visible en matriz: {'✅' if servicio.visible_en_matriz else '❌'}")

print("\n" + "=" * 80)
print("COMPLETADO")
print("=" * 80)
print("\n✨ Los slots han sido actualizados exitosamente")
print("   Ahora el calendario matriz mostrará los horarios correctos\n")