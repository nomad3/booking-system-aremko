#!/usr/bin/env python3
"""
Script para buscar todas las variaciones de Carmen Perez
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('=' * 80)
print('🔍 BÚSQUEDA AMPLIADA: TODOS LOS "CARMEN PEREZ"')
print('=' * 80)
print()

# Buscar todos los Carmen Perez
cur.execute('''
    SELECT id, nombre, telefono, email, documento_identidad, created_at
    FROM ventas_cliente
    WHERE LOWER(nombre) LIKE %s AND LOWER(nombre) LIKE %s
    ORDER BY nombre
''', ('%carmen%', '%perez%'))

clientes = cur.fetchall()

print(f'📊 TOTAL ENCONTRADOS: {len(clientes)} clientes\n')

for c in clientes:
    c_id, c_nombre, c_tel, c_email, c_doc, c_created = c

    # Servicios históricos
    cur.execute('''
        SELECT
            COUNT(*) as num_servicios,
            COALESCE(SUM(price_paid), 0) as total_gastado
        FROM crm_service_history
        WHERE cliente_id = %s
    ''', (c_id,))

    hist = cur.fetchone()
    num_serv, total_gasto = hist

    print('=' * 80)
    print(f'ID: {c_id} | {c_nombre}')
    print('=' * 80)
    print(f'   Teléfono: {c_tel}')
    print(f'   Email: {c_email}')
    print(f'   Documento: {c_doc}')
    print(f'   Servicios históricos: {num_serv} | Total: ${float(total_gasto):,.0f}')
    print(f'   Fecha creación: {c_created}')
    print()

cur.close()
conn.close()
