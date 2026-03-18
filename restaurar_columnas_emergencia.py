#!/usr/bin/env python
"""
SCRIPT DE EMERGENCIA: Restaura las columnas eliminadas para que funcione el sistema
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== RESTAURACIÓN DE EMERGENCIA ===\n")
print("⚠️  Este script restaura las columnas para que el sistema funcione\n")

try:
    with connection.cursor() as cursor:
        print("1. Restaurando columnas necesarias...")

        # Restaurar columna fecha
        try:
            cursor.execute("""
                ALTER TABLE ventas_serviciobloqueo
                ADD COLUMN IF NOT EXISTS fecha DATE
            """)
            print("   ✅ Columna 'fecha' restaurada")
        except Exception as e:
            print(f"   ⚠️  Error con 'fecha': {e}")

        # Restaurar columna hora_slot
        try:
            cursor.execute("""
                ALTER TABLE ventas_serviciobloqueo
                ADD COLUMN IF NOT EXISTS hora_slot VARCHAR(5)
            """)
            print("   ✅ Columna 'hora_slot' restaurada")
        except Exception as e:
            print(f"   ⚠️  Error con 'hora_slot': {e}")

        # Restaurar columna created_at
        try:
            cursor.execute("""
                ALTER TABLE ventas_serviciobloqueo
                ADD COLUMN IF NOT EXISTS created_at TIMESTAMP WITH TIME ZONE
            """)
            print("   ✅ Columna 'created_at' restaurada")
        except Exception as e:
            print(f"   ⚠️  Error con 'created_at': {e}")

        # Restaurar columna updated_at
        try:
            cursor.execute("""
                ALTER TABLE ventas_serviciobloqueo
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE
            """)
            print("   ✅ Columna 'updated_at' restaurada")
        except Exception as e:
            print(f"   ⚠️  Error con 'updated_at': {e}")

        # 2. Copiar datos de fecha_inicio a fecha
        print("\n2. Copiando datos a columnas restauradas...")
        cursor.execute("""
            UPDATE ventas_serviciobloqueo
            SET fecha = fecha_inicio
            WHERE fecha IS NULL
        """)
        print("   ✅ Copiados valores de fecha_inicio a fecha")

        # Copiar created_at
        cursor.execute("""
            UPDATE ventas_serviciobloqueo
            SET created_at = creado_en
            WHERE created_at IS NULL
        """)
        print("   ✅ Copiados valores de creado_en a created_at")

        # Copiar updated_at
        cursor.execute("""
            UPDATE ventas_serviciobloqueo
            SET updated_at = creado_en
            WHERE updated_at IS NULL
        """)
        print("   ✅ Copiados valores de creado_en a updated_at")

        # 3. Verificar
        print("\n3. Verificando estado final...")
        cursor.execute("""
            SELECT COUNT(*),
                   COUNT(fecha),
                   COUNT(created_at),
                   COUNT(updated_at)
            FROM ventas_serviciobloqueo
        """)

        total, con_fecha, con_created, con_updated = cursor.fetchone()
        print(f"   Total registros: {total}")
        print(f"   Con fecha: {con_fecha}")
        print(f"   Con created_at: {con_created}")
        print(f"   Con updated_at: {con_updated}")

        if con_fecha == total:
            print("\n✅ RESTAURACIÓN COMPLETADA")
            print("   El sistema debería funcionar ahora")
        else:
            print("\n⚠️  Advertencia: No todos los registros tienen fecha")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN RESTAURACIÓN ===")
print("\nNOTA: Esta es una solución temporal. El problema real es que")
print("el código Django espera estas columnas que no deberían existir.")