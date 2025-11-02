#!/usr/bin/env python3
"""
Script para analizar un teléfono específico y ver todos los clientes asociados
"""
import psycopg2
import os
import sys
from dotenv import load_dotenv

load_dotenv()

if len(sys.argv) < 2:
    print("Uso: python3 analizar_telefono.py +56XXXXXXXXX")
    sys.exit(1)

telefono = sys.argv[1]

conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

print('=' * 70)
print(f'📱 ANÁLISIS DEL TELÉFONO: {telefono}')
print('=' * 70)
print()

# Buscar todos los clientes con este teléfono
cur.execute('''
    SELECT id, nombre, email, documento_identidad, pais, comuna_id, created_at
    FROM ventas_cliente
    WHERE telefono = %s
    ORDER BY id
''', (telefono,))

clientes = cur.fetchall()

print(f'📊 CLIENTES ENCONTRADOS: {len(clientes)}')
print()

if not clientes:
    print('❌ No se encontraron clientes con este teléfono')
else:
    for i, (c_id, nombre, email, doc, pais, comuna_id, created) in enumerate(clientes, 1):
        print(f'{i}. CLIENTE ID: {c_id}')
        print(f'   Nombre: {nombre}')
        print(f'   Email: {email}')
        print(f'   Documento: {doc}')
        print(f'   País: {pais}')
        print(f'   Comuna ID: {comuna_id}')
        print(f'   Creado: {created}')

        # Buscar servicios históricos
        cur.execute('''
            SELECT
                service_type,
                service_name,
                service_date,
                quantity,
                price_paid,
                reserva_id
            FROM crm_service_history
            WHERE cliente_id = %s
            ORDER BY service_date DESC
        ''', (c_id,))

        servicios = cur.fetchall()

        print(f'   📋 Servicios históricos: {len(servicios)}')

        if servicios:
            print('   Últimos 5 servicios:')
            for svc_type, svc_name, svc_date, qty, price, reserva in servicios[:5]:
                print(f'      - {svc_date}: {svc_type} - {svc_name} (${float(price):,.0f}) [Reserva: {reserva}]')

            if len(servicios) > 5:
                print(f'      ... y {len(servicios) - 5} servicios más')

            # Total gastado
            cur.execute('''
                SELECT SUM(price_paid)
                FROM crm_service_history
                WHERE cliente_id = %s
            ''', (c_id,))
            total_gastado = cur.fetchone()[0]
            print(f'   💰 Total gastado: ${float(total_gastado):,.0f}')

        print()

# Resumen
print('=' * 70)
print('📊 RESUMEN')
print('=' * 70)

if len(clientes) > 1:
    print(f'⚠️  PROBLEMA DETECTADO:')
    print(f'   Este teléfono tiene {len(clientes)} clientes diferentes')
    print(f'   Los servicios históricos están dispersos entre ellos')
    print()

    total_servicios = 0
    total_gastado_global = 0
    for c_id, _, _, _, _, _, _ in clientes:
        cur.execute('SELECT COUNT(*), COALESCE(SUM(price_paid), 0) FROM crm_service_history WHERE cliente_id = %s', (c_id,))
        count, gastado = cur.fetchone()
        total_servicios += count
        total_gastado_global += float(gastado) if gastado else 0

    print(f'   Total servicios entre todos: {total_servicios}')
    print(f'   Total gastado entre todos: ${total_gastado_global:,.0f}')
    print()
    print('💡 RECOMENDACIÓN:')
    print('   - Los datos históricos tienen inconsistencias')
    print('   - Se recomienda limpiar y reimportar con CSV correcto')
else:
    print('✅ Este teléfono tiene un solo cliente (correcto)')

print('=' * 70)

cur.close()
conn.close()
