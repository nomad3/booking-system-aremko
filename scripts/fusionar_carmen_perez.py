#!/usr/bin/env python3
"""
Script para importar servicios de "Carmen Perez Meller"
y fusionarlos con "Carmen Perez Meyer" (ID: 4)
"""
import csv
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - Servicios Vendidos (1).csv"
DATABASE_URL = os.getenv('DATABASE_URL')
CARMEN_PEREZ_MEYER_ID = 4  # ID del cliente en ventas_cliente

def main():
    print("=" * 80)
    print("🔄 FUSIÓN: Carmen Perez Meller → Carmen Perez Meyer (ID: 4)")
    print("=" * 80)
    print()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    # 1. Verificar estado actual de Carmen Perez Meyer
    print("📋 PASO 1: Estado actual de Carmen Perez Meyer...")
    cur.execute('''
        SELECT COUNT(*), COALESCE(SUM(price_paid), 0)
        FROM crm_service_history
        WHERE cliente_id = %s
    ''', (CARMEN_PEREZ_MEYER_ID,))

    servicios_actuales, total_actual = cur.fetchone()
    print(f"   Servicios actuales: {servicios_actuales}")
    print(f"   Total actual: ${float(total_actual):,.0f}")
    print()

    # 2. Leer CSV y encontrar servicios de "Carmen Perez Meller"
    print("📋 PASO 2: Buscando servicios de 'Carmen Perez Meller' en CSV...")

    servicios_meller = []

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            cliente = row['cliente'].strip()

            if 'carmen' in cliente.lower() and 'perez' in cliente.lower() and 'meller' in cliente.lower():
                servicios_meller.append(row)

    print(f"   ✅ Encontrados: {len(servicios_meller)} servicios")
    print()

    # 3. Importar servicios
    print("📋 PASO 3: Importando servicios...")

    servicios_importados = 0
    servicios_ya_existentes = 0

    for row in servicios_meller:
        servicio = row['servicio'].strip()
        cantidad = int(row['cantidad']) if row['cantidad'] else 1
        valor = float(row['valor']) if row['valor'] else 0
        reserva_id = row['reserva'].strip() if row['reserva'] else None
        checkin_raw = row['checkin'].strip() if row['checkin'] else None
        categoria = row['categoria'].strip() if row['categoria'] else None

        # Manejo de fechas vacías
        if not checkin_raw or checkin_raw == '':
            checkin = '2020-01-01'
        else:
            checkin = checkin_raw

        # Manejo de categorías vacías
        if not categoria or categoria == '':
            categoria = 'Sin categoría'

        # Verificar si ya existe
        cur.execute('''
            SELECT id FROM crm_service_history
            WHERE cliente_id = %s AND reserva_id = %s AND service_name = %s
        ''', (CARMEN_PEREZ_MEYER_ID, reserva_id, servicio))

        if cur.fetchone():
            servicios_ya_existentes += 1
        else:
            # Insertar servicio
            cur.execute('''
                INSERT INTO crm_service_history
                (cliente_id, reserva_id, service_type, service_name, service_date, quantity, price_paid)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (CARMEN_PEREZ_MEYER_ID, reserva_id, categoria, servicio, checkin, cantidad, valor))

            servicios_importados += 1

    # COMMIT
    conn.commit()

    print(f"   ✅ Servicios nuevos importados: {servicios_importados}")
    print(f"   ⏭️  Servicios ya existentes (saltados): {servicios_ya_existentes}")
    print()

    # 4. Verificar estado FINAL
    print("📋 PASO 4: Estado final de Carmen Perez Meyer...")
    cur.execute('''
        SELECT COUNT(*), COALESCE(SUM(price_paid), 0)
        FROM crm_service_history
        WHERE cliente_id = %s
    ''', (CARMEN_PEREZ_MEYER_ID,))

    servicios_finales, total_final = cur.fetchone()
    print(f"   Servicios finales: {servicios_finales}")
    print(f"   Total final: ${float(total_final):,.0f}")
    print()

    print("=" * 80)
    print("📊 RESUMEN DE FUSIÓN")
    print("=" * 80)
    print(f"Servicios antes: {servicios_actuales} | ${float(total_actual):,.0f}")
    print(f"Servicios después: {servicios_finales} | ${float(total_final):,.0f}")
    print(f"Incremento: +{servicios_finales - servicios_actuales} servicios | +${float(total_final - total_actual):,.0f}")
    print()

    if servicios_importados > 0:
        print("✅ FUSIÓN COMPLETADA EXITOSAMENTE")
    else:
        print("ℹ️  No había servicios nuevos para fusionar")

    print("=" * 80)

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
