#!/usr/bin/env python
"""
Fix temporal para poder crear ServicioBloqueo
Hace opcionales los campos incorrectos mientras resolvemos el problema de fondo
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection
from ventas.models import ServicioBloqueo

print("=== FIX TEMPORAL SERVICIOBLOQUEO ===\n")
print("⚠️  Este fix permite crear ServicioBloqueo mientras resolvemos el problema de fondo\n")

try:
    with connection.cursor() as cursor:
        # 1. Verificar si existen las columnas problemáticas
        print("1. Verificando columnas problemáticas...")
        cursor.execute("""
            SELECT column_name, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'ventas_serviciobloqueo'
            AND column_name IN ('fecha', 'hora_slot')
        """)

        columnas = {row[0]: row[1] for row in cursor.fetchall()}

        if 'fecha' in columnas:
            print(f"   - fecha existe (nullable: {columnas['fecha']})")

            if columnas['fecha'] == 'NO':
                print("   Haciendo 'fecha' opcional...")
                cursor.execute("""
                    ALTER TABLE ventas_serviciobloqueo
                    ALTER COLUMN fecha DROP NOT NULL
                """)
                print("   ✅ 'fecha' ahora es opcional")

        if 'hora_slot' in columnas:
            print(f"   - hora_slot existe (nullable: {columnas['hora_slot']})")

            if columnas['hora_slot'] == 'NO':
                print("   Haciendo 'hora_slot' opcional...")
                # Primero actualizar valores vacíos
                cursor.execute("""
                    UPDATE ventas_serviciobloqueo
                    SET hora_slot = 'N/A'
                    WHERE hora_slot = '' OR hora_slot IS NULL
                """)
                # Hacer opcional
                cursor.execute("""
                    ALTER TABLE ventas_serviciobloqueo
                    ALTER COLUMN hora_slot DROP NOT NULL
                """)
                # Establecer default
                cursor.execute("""
                    ALTER TABLE ventas_serviciobloqueo
                    ALTER COLUMN hora_slot SET DEFAULT 'N/A'
                """)
                print("   ✅ 'hora_slot' ahora es opcional con default 'N/A'")

        # 2. Verificar resultado
        print("\n2. Verificando cambios...")
        cursor.execute("""
            SELECT column_name, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'ventas_serviciobloqueo'
            AND column_name IN ('fecha', 'hora_slot', 'fecha_inicio', 'fecha_fin')
            ORDER BY column_name
        """)

        print("   Estado actual:")
        for row in cursor.fetchall():
            print(f"   - {row[0]}: nullable={row[1]}, default={row[2]}")

        print("\n✅ FIX TEMPORAL APLICADO")
        print("\nAhora deberías poder crear ServicioBloqueo:")
        print("- Los campos correctos son: fecha_inicio, fecha_fin")
        print("- Los campos incorrectos (fecha, hora_slot) son opcionales")
        print("\n⚠️  IMPORTANTE: Este es un fix temporal. El problema de fondo")
        print("es que el modelo tiene campos y métodos mezclados.")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN FIX TEMPORAL ===")