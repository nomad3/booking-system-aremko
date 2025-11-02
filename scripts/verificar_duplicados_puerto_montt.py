#!/usr/bin/env python
"""
Script para verificar duplicados de Puerto Montt en la tabla Comuna
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from ventas.models import Comuna, Region, Cliente

# Buscar todas las comunas que contengan "Puerto Mont"
comunas_pm = Comuna.objects.filter(nombre__icontains='puerto mont').select_related('region')

print("=" * 60)
print("COMUNAS CON 'PUERTO MONT' EN LA BASE DE DATOS")
print("=" * 60)
for comuna in comunas_pm:
    print(f"ID: {comuna.id:3d} | Nombre: '{comuna.nombre:20s}' | Región: {comuna.region.nombre}")

print("\n" + "=" * 60)
print("CLIENTES POR CADA VARIANTE")
print("=" * 60)
for comuna in comunas_pm:
    count = Cliente.objects.filter(comuna=comuna).count()
    print(f"'{comuna.nombre}' (ID {comuna.id}): {count:4d} clientes")

print("\n" + "=" * 60)
print("TOTAL DE COMUNAS EN REGIÓN DE LOS LAGOS")
print("=" * 60)
region_lagos = Region.objects.get(codigo='X')
total_comunas = Comuna.objects.filter(region=region_lagos).count()
print(f"Total: {total_comunas} comunas")
