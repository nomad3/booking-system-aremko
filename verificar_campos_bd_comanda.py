#!/usr/bin/env python
"""
Script para verificar campos en la BD que podrían causar error al guardar comandas
Ejecutar con: python manage.py shell < verificar_campos_bd_comanda.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import connection

print("\n=== VERIFICACIÓN DE CAMPOS EN BASE DE DATOS ===\n")

# Función para verificar tabla
def verificar_tabla(nombre_tabla, campos_esperados):
    print(f"\nVerificando tabla: {nombre_tabla}")
    print("-" * 50)

    with connection.cursor() as cursor:
        # Obtener columnas actuales
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, [nombre_tabla])

        columnas = {row[0]: {
            'tipo': row[1],
            'nullable': row[2],
            'default': row[3]
        } for row in cursor.fetchall()}

        # Verificar campos esperados
        for campo in campos_esperados:
            if campo in columnas:
                info = columnas[campo]
                print(f"  ✓ {campo}: {info['tipo']} (null={info['nullable']})")
            else:
                print(f"  ✗ {campo}: FALTA EN LA BD")

        # Mostrar campos extra no esperados
        campos_extra = set(columnas.keys()) - set(campos_esperados) - {'id'}
        if campos_extra:
            print(f"\n  Campos adicionales encontrados:")
            for campo in campos_extra:
                info = columnas[campo]
                print(f"    - {campo}: {info['tipo']}")

# 1. Verificar tabla ventas_comanda
campos_comanda = [
    'id',
    'venta_reserva_id',
    'fecha_solicitud',
    'hora_solicitud',
    'estado',
    'notas_generales',
    'usuario_solicita_id',
    'usuario_procesa_id',
    'fecha_inicio_proceso',
    'fecha_entrega',
    'fecha_entrega_objetivo',
    'lugar_entrega',
    'es_urgente',
    'tiempo_preparacion_estimado',
    'numero_comanda',
    'total_items',
    'total_precio'
]

verificar_tabla('ventas_comanda', campos_comanda)

# 2. Verificar tabla ventas_detallecomanda
campos_detalle = [
    'id',
    'comanda_id',
    'producto_id',
    'cantidad',
    'especificaciones',
    'precio_unitario',
    'estado',
    'notas_preparacion'
]

verificar_tabla('ventas_detallecomanda', campos_detalle)

# 3. Verificar tabla ventas_reservaproducto
campos_reserva_producto = [
    'id',
    'venta_reserva_id',
    'producto_id',
    'cantidad',
    'precio_unitario_venta',
    'fecha_entrega',
    'regalo_para',
    'incluir_propina',
    'porcentaje_propina',
    'descuento_aplicado',
    'precio_con_descuento'
]

verificar_tabla('ventas_reservaproducto', campos_reserva_producto)

# 4. Verificar constraints y relaciones
print("\n\nVerificando constraints y relaciones")
print("-" * 50)

with connection.cursor() as cursor:
    # Verificar foreign keys
    cursor.execute("""
        SELECT
            tc.constraint_name,
            tc.table_name,
            kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
            ON tc.constraint_name = kcu.constraint_name
        JOIN information_schema.constraint_column_usage AS ccu
            ON ccu.constraint_name = tc.constraint_name
        WHERE tc.table_name IN ('ventas_comanda', 'ventas_detallecomanda', 'ventas_reservaproducto')
            AND tc.constraint_type = 'FOREIGN KEY'
        ORDER BY tc.table_name, kcu.column_name
    """)

    print("\nForeign Keys:")
    for row in cursor.fetchall():
        print(f"  - {row[1]}.{row[2]} → {row[3]}.{row[4]}")

    # Verificar índices únicos
    cursor.execute("""
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef
        FROM pg_indexes
        WHERE tablename IN ('ventas_comanda', 'ventas_detallecomanda', 'ventas_reservaproducto')
            AND indexdef LIKE '%UNIQUE%'
        ORDER BY tablename, indexname
    """)

    print("\nÍndices únicos:")
    indices = cursor.fetchall()
    if indices:
        for row in indices:
            print(f"  - {row[1]}: {row[2]}")
    else:
        print("  (No se encontraron índices únicos)")

# 5. Verificar valores NULL problemáticos
print("\n\nVerificando registros con valores NULL problemáticos")
print("-" * 50)

with connection.cursor() as cursor:
    # Comandas sin venta_reserva
    cursor.execute("SELECT COUNT(*) FROM ventas_comanda WHERE venta_reserva_id IS NULL")
    count = cursor.fetchone()[0]
    print(f"  Comandas sin venta_reserva: {count}")

    # Detalles sin producto o comanda
    cursor.execute("SELECT COUNT(*) FROM ventas_detallecomanda WHERE producto_id IS NULL OR comanda_id IS NULL")
    count = cursor.fetchone()[0]
    print(f"  Detalles sin producto o comanda: {count}")

    # ReservaProducto sin campos requeridos
    cursor.execute("""
        SELECT COUNT(*)
        FROM ventas_reservaproducto
        WHERE venta_reserva_id IS NULL
           OR producto_id IS NULL
           OR cantidad IS NULL
           OR precio_unitario_venta IS NULL
    """)
    count = cursor.fetchone()[0]
    print(f"  ReservaProducto con campos NULL críticos: {count}")

print("\n=== VERIFICACIÓN COMPLETADA ===\n")