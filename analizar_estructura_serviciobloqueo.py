#!/usr/bin/env python
"""
Analizar la estructura real de la tabla ServicioBloqueo en la BD
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from ventas.models import ServicioBloqueo

print("=== ANÁLISIS ESTRUCTURA SERVICIOBLOQUEO ===\n")

# 1. Ver columnas en la base de datos
print("1. Columnas en la tabla de la base de datos:")
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'ventas_serviciobloqueo'
        ORDER BY ordinal_position
    """)

    columnas_bd = cursor.fetchall()
    for col in columnas_bd:
        print(f"   - {col[0]}: {col[1]} (null: {col[2]}, default: {col[3]})")

# 2. Ver campos esperados por Django
print("\n2. Campos que Django espera (desde el modelo):")
for field in ServicioBloqueo._meta.get_fields():
    if hasattr(field, 'column'):
        required = "requerido" if not field.null else "opcional"
        print(f"   - {field.name} ({field.column}): {required}")

# 3. Comparar
print("\n3. Análisis de discrepancias:")
columnas_bd_nombres = {col[0] for col in columnas_bd}
campos_django = {field.column for field in ServicioBloqueo._meta.get_fields() if hasattr(field, 'column')}

solo_en_bd = columnas_bd_nombres - campos_django
solo_en_django = campos_django - columnas_bd_nombres

if solo_en_bd:
    print(f"   ❌ Columnas en BD pero NO en Django: {solo_en_bd}")
if solo_en_django:
    print(f"   ❌ Campos en Django pero NO en BD: {solo_en_django}")
if not solo_en_bd and not solo_en_django:
    print("   ✅ Estructura sincronizada")

# 4. Ver el código del método save
print("\n4. Método save() actual de ServicioBloqueo:")
import inspect
try:
    print(inspect.getsource(ServicioBloqueo.save))
except:
    print("   No tiene método save() personalizado")

# 5. Ver el código del método clean
print("\n5. Método clean() actual de ServicioBloqueo:")
try:
    print(inspect.getsource(ServicioBloqueo.clean))
except:
    print("   No tiene método clean() personalizado")

print("\n=== FIN ANÁLISIS ===")