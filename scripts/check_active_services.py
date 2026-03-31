#!/usr/bin/env python
"""
Script para listar servicios activos y sus capacidades
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, '/app')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Servicio

print("\n" + "="*80)
print("SERVICIOS ACTIVOS EN EL SISTEMA")
print("="*80)

servicios = Servicio.objects.filter(activo=True).order_by('tipo_servicio', 'nombre')

print(f"\nTotal de servicios activos: {servicios.count()}\n")

for servicio in servicios:
    print(f"ID: {servicio.id:3d} | {servicio.nombre:40s} | Tipo: {servicio.tipo_servicio:10s} | Cap: {servicio.capacidad_minima}-{servicio.capacidad_maxima} personas | Precio: ${servicio.precio_base:,.0f}")

print("\n" + "="*80)
