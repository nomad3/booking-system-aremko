#!/usr/bin/env python3
"""
Script para analizar la estructura y duplicados en crm_service_history
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('=' * 70)
print('📋 ESTRUCTURA DE crm_service_history')
print('=' * 70)
print()

# Obtener estructura de la tabla
cur.execute('''
    SELECT
        column_name,
        data_type,
        character_maximum_length,
        is_nullable
    FROM information_schema.columns
    WHERE table_name = 'crm_service_history'
    ORDER BY ordinal_position;
''')

columns = cur.fetchall()
print('Columnas de la tabla:')
for col_name, col_type, max_len, nullable in columns:
    len_info = f'({max_len})' if max_len else ''
    null_info = 'NULL' if nullable == 'YES' else 'NOT NULL'
    print(f'  - {col_name}: {col_type}{len_info} {null_info}')

print()
print('=' * 70)
print('📊 MUESTRA DE DATOS (5 registros)')
print('=' * 70)
print()

# Obtener muestra de datos
cur.execute('SELECT * FROM crm_service_history LIMIT 5')
rows = cur.fetchall()

col_names = [desc[0] for desc in cur.description]

for i, row in enumerate(rows, 1):
    print(f'Registro {i}:')
    for col_name, value in zip(col_names, row):
        print(f'  {col_name}: {value}')
    print()

# Análisis de duplicados si hay un campo nombre_cliente
print('=' * 70)
print('🔍 ANÁLISIS DE NOMBRES POR TELÉFONO')
print('=' * 70)
print()

# Verificar si existe campo nombre_cliente o similar
cur.execute('''
    SELECT column_name
    FROM information_schema.columns
    WHERE table_name = 'crm_service_history'
    AND (column_name LIKE '%nombre%' OR column_name LIKE '%client%')
''')
nombre_cols = cur.fetchall()

if nombre_cols:
    print(f'Columnas de nombre encontradas: {[c[0] for c in nombre_cols]}')
    print()

    # Si hay un campo de nombre, buscar inconsistencias
    nombre_col = nombre_cols[0][0]

    cur.execute(f'''
        SELECT
            sh.telefono_cliente,
            sh.{nombre_col},
            c.nombre as nombre_actual,
            COUNT(*) as num_servicios
        FROM crm_service_history sh
        LEFT JOIN ventas_cliente c ON sh.telefono_cliente = c.telefono
        WHERE sh.{nombre_col} != c.nombre OR c.nombre IS NULL
        GROUP BY sh.telefono_cliente, sh.{nombre_col}, c.nombre
        LIMIT 20
    ''')

    inconsistencias = cur.fetchall()

    if inconsistencias:
        print(f'⚠️  INCONSISTENCIAS ENCONTRADAS: {len(inconsistencias)} casos')
        print()
        for tel, nombre_hist, nombre_actual, num_serv in inconsistencias[:10]:
            print(f'Teléfono: {tel}')
            print(f'  Nombre en histórico: {nombre_hist}')
            print(f'  Nombre actual: {nombre_actual}')
            print(f'  Servicios: {num_serv}')
            print()
else:
    print('No se encontraron columnas de nombre en la tabla')
    print('Analizando por cliente_id...')
    print()

    # Análisis por cliente_id
    cur.execute('''
        SELECT
            c.telefono,
            COUNT(DISTINCT c.id) as num_clientes,
            STRING_AGG(DISTINCT c.nombre, ', ') as nombres,
            COUNT(sh.id) as num_servicios
        FROM crm_service_history sh
        JOIN ventas_cliente c ON sh.cliente_id = c.id
        GROUP BY c.telefono
        HAVING COUNT(DISTINCT c.id) > 1
        LIMIT 20
    ''')

    duplicados = cur.fetchall()

    if duplicados:
        print(f'⚠️  TELÉFONOS CON MÚLTIPLES CLIENTES: {len(duplicados)} casos')
        print()
        for tel, num_clientes, nombres, num_serv in duplicados[:10]:
            print(f'Teléfono: {tel}')
            print(f'  Clientes diferentes: {num_clientes}')
            print(f'  Nombres: {nombres}')
            print(f'  Total servicios: {num_serv}')
            print()
    else:
        print('✅ No se encontraron duplicados evidentes')

cur.close()
conn.close()
