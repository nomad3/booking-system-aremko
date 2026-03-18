#!/usr/bin/env python
"""
Script para verificar el estado real de los modelos de bloqueo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from ventas.models import ServicioBloqueo, ServicioSlotBloqueo

print("=== VERIFICACIÓN DE MODELOS DE BLOQUEO ===\n")

# 1. Verificar las tablas en la base de datos
print("1. Tablas en la base de datos:")
with connection.cursor() as cursor:
    # Para PostgreSQL
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name LIKE 'ventas_%bloqueo%'
    """)
    tablas = cursor.fetchall()
    for tabla in tablas:
        print(f"   - {tabla[0]}")

# 2. Verificar columnas de ventas_serviciobloqueo
print("\n2. Columnas de ventas_serviciobloqueo:")
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ventas_serviciobloqueo'
        ORDER BY ordinal_position
    """)
    columnas = cursor.fetchall()
    for col in columnas:
        print(f"   - {col[0]}: {col[1]} (null: {col[2]})")

# 3. Verificar columnas de ventas_servicioslotbloqueo
print("\n3. Columnas de ventas_servicioslotbloqueo:")
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'ventas_servicioslotbloqueo'
        ORDER BY ordinal_position
    """)
    columnas = cursor.fetchall()
    for col in columnas:
        print(f"   - {col[0]}: {col[1]} (null: {col[2]})")

# 4. Comparar con los modelos de Django
print("\n4. Campos del modelo ServicioBloqueo en Django:")
for field in ServicioBloqueo._meta.get_fields():
    if not field.many_to_many and not field.one_to_many:
        print(f"   - {field.name}: {field.__class__.__name__}")

print("\n5. Campos del modelo ServicioSlotBloqueo en Django:")
for field in ServicioSlotBloqueo._meta.get_fields():
    if not field.many_to_many and not field.one_to_many:
        print(f"   - {field.name}: {field.__class__.__name__}")

print("\n=== FIN VERIFICACIÓN ===")