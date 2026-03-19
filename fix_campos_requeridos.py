#!/usr/bin/env python
"""
Script para hacer que los campos incorrectos sean opcionales
Solución temporal para poder crear ServicioBloqueo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== FIX TEMPORAL: CAMPOS OPCIONALES ===\n")

try:
    with connection.cursor() as cursor:
        # 1. Hacer fecha opcional (nullable)
        print("1. Haciendo campo 'fecha' opcional...")
        cursor.execute("""
            ALTER TABLE ventas_serviciobloqueo
            ALTER COLUMN fecha DROP NOT NULL
        """)
        print("   ✅ Campo 'fecha' ahora es opcional")

        # 2. Hacer hora_slot opcional y darle un valor por defecto
        print("\n2. Haciendo campo 'hora_slot' opcional...")

        # Primero actualizar los valores vacíos
        cursor.execute("""
            UPDATE ventas_serviciobloqueo
            SET hora_slot = 'N/A'
            WHERE hora_slot = '' OR hora_slot IS NULL
        """)
        print("   ✅ Valores vacíos actualizados a 'N/A'")

        # Hacer el campo opcional
        cursor.execute("""
            ALTER TABLE ventas_serviciobloqueo
            ALTER COLUMN hora_slot DROP NOT NULL
        """)
        print("   ✅ Campo 'hora_slot' ahora es opcional")

        # 3. Establecer un valor por defecto
        cursor.execute("""
            ALTER TABLE ventas_serviciobloqueo
            ALTER COLUMN hora_slot SET DEFAULT 'N/A'
        """)
        print("   ✅ Valor por defecto establecido: 'N/A'")

        # 4. Verificar
        print("\n3. Verificando cambios...")
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'ventas_serviciobloqueo'
            AND column_name IN ('fecha', 'hora_slot')
        """)

        for row in cursor.fetchall():
            print(f"   {row[0]}: nullable={row[1]}, default={row[2]}")

        print("\n✅ FIX APLICADO")
        print("\nAhora deberías poder crear ServicioBloqueo:")
        print("- El campo 'fecha' se llenará automáticamente con fecha_inicio")
        print("- El campo 'hora_slot' se llenará con 'N/A'")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN FIX TEMPORAL ===")