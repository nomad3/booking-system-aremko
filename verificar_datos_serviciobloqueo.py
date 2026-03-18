#!/usr/bin/env python
"""
Script para VERIFICAR datos en columnas incorrectas de ServicioBloqueo
NO MODIFICA NADA, solo consulta
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== VERIFICACIÓN DE DATOS EN SERVICIOBLOQUEO ===\n")
print("⚠️  Este script SOLO CONSULTA, no modifica nada\n")

try:
    with connection.cursor() as cursor:
        # 1. Contar registros totales
        cursor.execute("SELECT COUNT(*) FROM ventas_serviciobloqueo")
        total = cursor.fetchone()[0]
        print(f"1. Total de registros en ServicioBloqueo: {total}")

        # 2. Verificar datos en columnas incorrectas
        print("\n2. Datos en columnas que NO deberían existir:")

        # Verificar cada columna
        for columna in ['fecha', 'hora_slot', 'created_at', 'updated_at']:
            try:
                cursor.execute(f"""
                    SELECT COUNT(*)
                    FROM ventas_serviciobloqueo
                    WHERE {columna} IS NOT NULL
                """)
                count = cursor.fetchone()[0]
                print(f"   - {columna}: {count} registros con datos")

                # Si hay datos, mostrar algunos ejemplos
                if count > 0 and count <= 5:
                    cursor.execute(f"""
                        SELECT id, {columna}, servicio_id, fecha_inicio, fecha_fin
                        FROM ventas_serviciobloqueo
                        WHERE {columna} IS NOT NULL
                        LIMIT 5
                    """)
                    print(f"     Ejemplos:")
                    for row in cursor.fetchall():
                        print(f"     ID {row[0]}: {columna}={row[1]}, servicio_id={row[2]}, rango={row[3]} a {row[4]}")

            except Exception as e:
                print(f"   - {columna}: No existe esta columna")

        # 3. Mostrar algunos registros completos como ejemplo
        print("\n3. Ejemplo de registros actuales (primeros 3):")
        cursor.execute("""
            SELECT id, servicio_id, fecha_inicio, fecha_fin, motivo, activo
            FROM ventas_serviciobloqueo
            LIMIT 3
        """)

        registros = cursor.fetchall()
        if registros:
            for reg in registros:
                print(f"   ID {reg[0]}: Servicio {reg[1]}, {reg[2]} a {reg[3]}, Motivo: '{reg[4]}', Activo: {reg[5]}")
        else:
            print("   No hay registros en la tabla")

        # 4. Verificar si hay bloqueos activos actualmente
        print("\n4. Bloqueos activos actualmente:")
        from datetime import date
        hoy = date.today()

        cursor.execute("""
            SELECT COUNT(*)
            FROM ventas_serviciobloqueo
            WHERE activo = true
            AND fecha_inicio <= %s
            AND fecha_fin >= %s
        """, [hoy, hoy])

        activos_hoy = cursor.fetchone()[0]
        print(f"   Bloqueos activos hoy: {activos_hoy}")

        # 5. Resumen y recomendación
        print("\n5. RESUMEN:")
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN fecha IS NOT NULL THEN 1 END) as con_fecha,
                COUNT(CASE WHEN hora_slot IS NOT NULL THEN 1 END) as con_hora_slot
            FROM ventas_serviciobloqueo
        """)
        resumen = cursor.fetchone()

        if resumen[0] > 0 or resumen[1] > 0:
            print("   ⚠️  HAY DATOS en columnas incorrectas:")
            print(f"   - Registros con 'fecha': {resumen[0]}")
            print(f"   - Registros con 'hora_slot': {resumen[1]}")
            print("\n   RECOMENDACIÓN: Investigar estos datos antes de eliminar columnas")
        else:
            print("   ✅ NO HAY DATOS en las columnas incorrectas")
            print("   Es seguro eliminar las columnas fecha, hora_slot, created_at, updated_at")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN VERIFICACIÓN ===")
print("\nNOTA: No se modificó ningún dato")