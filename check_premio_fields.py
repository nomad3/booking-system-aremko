#!/usr/bin/env python
"""
Script para verificar la estructura de la tabla Premio en producción
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from django.db import connection
from ventas.models import Premio

print("=== VERIFICANDO TABLA PREMIO ===\n")

# Ver las columnas de la tabla
with connection.cursor() as cursor:
    cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'ventas_premio' ORDER BY ordinal_position")
    columns = cursor.fetchall()
    print("Columnas en la tabla ventas_premio:")
    for col in columns:
        print(f"  - {col[0]}")

print("\n=== VERIFICANDO CAMPO tramos_validos ===")
# Verificar si la columna tramos_validos existe en la BD
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'ventas_premio'
        AND column_name = 'tramos_validos'
    """)
    result = cursor.fetchone()
    if result:
        print("✅ La columna 'tramos_validos' EXISTE en la base de datos")
    else:
        print("❌ La columna 'tramos_validos' NO EXISTE en la base de datos")
        print("   Necesitas crear y aplicar la migración")

print("\n=== DATOS DE PREMIOS ===")
# Verificar si podemos acceder al campo
try:
    premios = Premio.objects.all()
    print(f"Total de premios: {premios.count()}")

    for premio in premios[:3]:  # Mostrar los primeros 3
        print(f"\n- Premio: {premio.nombre}")
        print(f"  Tipo: {premio.tipo}")
        print(f"  tramo_hito: {premio.tramo_hito}")
        if hasattr(premio, 'tramos_validos'):
            print(f"  tramos_validos: {premio.tramos_validos}")
        else:
            print("  tramos_validos: Campo no disponible")

except Exception as e:
    print(f"Error al acceder a los premios: {e}")

print("\n=== RESUMEN ===")
print("Si la columna 'tramos_validos' no existe, necesitas:")
print("1. Crear la migración manualmente")
print("2. Aplicar la migración")
print("3. Ejecutar el comando configurar_tramos_premios")