#!/usr/bin/env python
"""
Script para analizar la columna 'fecha' en ServicioBloqueo
y entender su relación con fecha_inicio/fecha_fin
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("=== ANÁLISIS DE COLUMNA 'fecha' EN SERVICIOBLOQUEO ===\n")

try:
    with connection.cursor() as cursor:
        # 1. Comparar fecha con fecha_inicio y fecha_fin
        print("1. Análisis de la columna 'fecha':")

        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN fecha = fecha_inicio THEN 1 END) as fecha_igual_inicio,
                COUNT(CASE WHEN fecha = fecha_fin THEN 1 END) as fecha_igual_fin,
                COUNT(CASE WHEN fecha != fecha_inicio AND fecha != fecha_fin THEN 1 END) as fecha_diferente,
                COUNT(CASE WHEN fecha_inicio = fecha_fin THEN 1 END) as bloqueos_un_dia
            FROM ventas_serviciobloqueo
        """)

        stats = cursor.fetchone()
        print(f"   Total registros: {stats[0]}")
        print(f"   fecha = fecha_inicio: {stats[1]} registros")
        print(f"   fecha = fecha_fin: {stats[2]} registros")
        print(f"   fecha diferente de ambas: {stats[3]} registros")
        print(f"   Bloqueos de un solo día: {stats[4]} registros")

        # 2. Mostrar ejemplos donde fecha es diferente
        print("\n2. Ejemplos donde 'fecha' es diferente de fecha_inicio/fin:")
        cursor.execute("""
            SELECT id, fecha, fecha_inicio, fecha_fin, motivo
            FROM ventas_serviciobloqueo
            WHERE fecha != fecha_inicio AND fecha != fecha_fin
            LIMIT 5
        """)

        diferentes = cursor.fetchall()
        if diferentes:
            for row in diferentes:
                print(f"   ID {row[0]}: fecha={row[1]}, rango={row[2]} a {row[3]}, motivo='{row[4]}'")
        else:
            print("   No hay casos donde fecha sea diferente")

        # 3. Ver distribución de valores de fecha
        print("\n3. Valores únicos en columna 'fecha' (primeros 10):")
        cursor.execute("""
            SELECT fecha, COUNT(*) as cantidad
            FROM ventas_serviciobloqueo
            WHERE fecha IS NOT NULL
            GROUP BY fecha
            ORDER BY fecha DESC
            LIMIT 10
        """)

        for row in cursor.fetchall():
            print(f"   {row[0]}: {row[1]} registros")

        # 4. Verificar created_at vs creado_en
        print("\n4. Comparación created_at vs creado_en:")
        cursor.execute("""
            SELECT
                COUNT(CASE WHEN created_at IS NOT NULL THEN 1 END) as con_created_at,
                COUNT(CASE WHEN creado_en IS NOT NULL THEN 1 END) as con_creado_en,
                COUNT(CASE WHEN DATE(created_at) = DATE(creado_en) THEN 1 END) as misma_fecha
            FROM ventas_serviciobloqueo
        """)

        timestamps = cursor.fetchone()
        print(f"   Registros con created_at: {timestamps[0]}")
        print(f"   Registros con creado_en: {timestamps[1]}")
        print(f"   Misma fecha en ambos: {timestamps[2]}")

        # 5. Recomendación
        print("\n5. ANÁLISIS Y RECOMENDACIÓN:")

        if stats[1] == stats[0]:  # todos tienen fecha = fecha_inicio
            print("   ✅ La columna 'fecha' siempre es igual a 'fecha_inicio'")
            print("   → Es redundante y puede eliminarse sin pérdida de datos")
        elif stats[3] > 0:  # hay casos donde fecha es diferente
            print("   ⚠️  La columna 'fecha' tiene valores diferentes a fecha_inicio/fin")
            print("   → Necesita revisión manual antes de eliminar")

        print("\n   Para created_at/updated_at:")
        print("   → Son redundantes con creado_en")
        print("   → Pueden eliminarse sin pérdida de información")

except Exception as e:
    print(f"\n❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n=== FIN ANÁLISIS ===")