#!/usr/bin/env python
"""
Script para verificar campos reales del modelo Cliente
Ejecutar: python scripts/check_cliente_fields.py
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

from ventas.models import Cliente
from django.db import connection

print("\n" + "="*60)
print("CAMPOS DEL MODELO CLIENTE")
print("="*60)

print("\n📋 Campos definidos en el modelo Django:")
print("-" * 60)

for field in Cliente._meta.get_fields():
    field_type = type(field).__name__

    # Verificar si es campo de la tabla o relación
    if hasattr(field, 'column'):
        column_name = field.column
        print(f"✅ {field.name:30s} | Tipo: {field_type:20s} | Columna: {column_name}")
    else:
        print(f"↔️  {field.name:30s} | Tipo: {field_type:20s} | (Relación inversa)")

print("\n" + "="*60)
print("COLUMNAS REALES EN LA BASE DE DATOS")
print("="*60)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'ventas_cliente'
        ORDER BY ordinal_position
    """)

    columns = cursor.fetchall()

    print("\n📊 Columnas en la tabla 'ventas_cliente':")
    print("-" * 60)

    for col_name, data_type, is_nullable in columns:
        nullable = "NULL" if is_nullable == "YES" else "NOT NULL"
        print(f"✅ {col_name:30s} | {data_type:20s} | {nullable}")

print("\n" + "="*60)
print("VERIFICACIÓN ESPECÍFICA: documento_identidad")
print("="*60)

# Verificar si documento_identidad existe en el modelo
if hasattr(Cliente, 'documento_identidad'):
    print("\n✅ Campo 'documento_identidad' EXISTE en el modelo Django")
    field = Cliente._meta.get_field('documento_identidad')
    print(f"   Tipo: {type(field).__name__}")
    print(f"   Columna en BD: {field.column}")
    print(f"   Null: {field.null}")
    print(f"   Blank: {field.blank}")
else:
    print("\n❌ Campo 'documento_identidad' NO existe en el modelo Django")

# Verificar si existe en la base de datos
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'ventas_cliente'
        AND column_name = 'documento_identidad'
    """)

    result = cursor.fetchone()

    if result:
        print(f"\n✅ Columna 'documento_identidad' EXISTE en la tabla ventas_cliente")
    else:
        print(f"\n❌ Columna 'documento_identidad' NO existe en la tabla ventas_cliente")
        print("\n⚠️  ACCIÓN REQUERIDA:")
        print("   Necesitamos crear y aplicar una migración para agregar este campo")

print("\n" + "="*60)
print("RESUMEN")
print("="*60)

# Verificar discrepancias
model_fields = set([f.name for f in Cliente._meta.get_fields() if hasattr(f, 'column')])

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'ventas_cliente'
    """)

    db_columns = set([row[0] for row in cursor.fetchall()])

# Campos en modelo pero no en BD
missing_in_db = model_fields - db_columns
if missing_in_db:
    print(f"\n⚠️  Campos en modelo pero NO en BD: {missing_in_db}")
    print("   Necesitas crear y aplicar migraciones")
else:
    print(f"\n✅ Todos los campos del modelo existen en la BD")

# Columnas en BD pero no en modelo
extra_in_db = db_columns - model_fields
if extra_in_db:
    print(f"\n📝 Columnas en BD pero no en modelo (legacy): {extra_in_db}")

print("\n" + "="*60)