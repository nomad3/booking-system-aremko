#!/usr/bin/env python3
"""
Script para analizar el caso de Katherine Salazar Troncoso
Comparar datos del perfil vs segmentación
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

TELEFONO = '+56950526439'
EMAIL = 'ksalazart@gmail.com'

def main():
    print("=" * 80)
    print("🔍 ANÁLISIS: Katherine Salazar Troncoso")
    print("=" * 80)
    print(f"Teléfono: {TELEFONO}")
    print(f"Email: {EMAIL}")
    print()

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()

    # 1. Buscar TODOS los clientes con este teléfono
    print("📋 PASO 1: Buscando clientes con este teléfono...")
    cur.execute('''
        SELECT id, nombre, telefono, email, documento_identidad, created_at
        FROM ventas_cliente
        WHERE telefono = %s
        ORDER BY id
    ''', (TELEFONO,))

    clientes = cur.fetchall()
    print(f"   ✅ Clientes encontrados: {len(clientes)}")
    print()

    if len(clientes) > 1:
        print("   ⚠️  ALERTA: Múltiples clientes con el mismo teléfono!")
        print()

    total_servicios_global = 0
    total_gasto_global = 0

    # 2. Por cada cliente, obtener servicios
    for cliente in clientes:
        cliente_id, nombre, telefono, email, doc, created = cliente

        print("=" * 80)
        print(f"Cliente ID: {cliente_id}")
        print(f"Nombre: {nombre}")
        print(f"Email: {email}")
        print(f"Documento: {doc}")
        print(f"Fecha creación: {created}")
        print("=" * 80)
        print()

        # Servicios históricos
        cur.execute('''
            SELECT
                COUNT(*) as num_servicios,
                COALESCE(SUM(price_paid), 0) as total_gastado
            FROM crm_service_history
            WHERE cliente_id = %s
        ''', (cliente_id,))

        hist = cur.fetchone()
        num_servicios, total_gasto = hist

        print(f"📊 SERVICIOS HISTÓRICOS:")
        print(f"   Cantidad: {num_servicios}")
        print(f"   Total: ${float(total_gasto):,.0f}")
        print()

        total_servicios_global += num_servicios
        total_gasto_global += float(total_gasto)

        # Listar TODOS los servicios
        if num_servicios > 0:
            cur.execute('''
                SELECT id, reserva_id, service_type, service_name, service_date, quantity, price_paid
                FROM crm_service_history
                WHERE cliente_id = %s
                ORDER BY service_date DESC, id DESC
            ''', (cliente_id,))

            servicios = cur.fetchall()

            print(f"📋 DETALLE DE SERVICIOS ({len(servicios)} registros):")
            print()

            for i, s in enumerate(servicios, 1):
                s_id, reserva, tipo, nombre_serv, fecha, cantidad, precio = s
                print(f"   {i}. [{fecha}] {tipo} - {nombre_serv}")
                print(f"      ID: {s_id} | Reserva: {reserva} | Cantidad: {cantidad} | Precio: ${float(precio):,.0f}")
                print()

    # 3. RESUMEN GLOBAL
    print("=" * 80)
    print("📊 RESUMEN GLOBAL")
    print("=" * 80)
    print(f"Total clientes con teléfono {TELEFONO}: {len(clientes)}")
    print(f"Total servicios acumulados: {total_servicios_global}")
    print(f"Total gasto acumulado: ${total_gasto_global:,.0f}")
    print()

    # 4. COMPARACIÓN CON DATOS ESPERADOS
    print("=" * 80)
    print("🔍 COMPARACIÓN CON SEGMENTACIÓN")
    print("=" * 80)
    print(f"Segmentación dice: $550,000 total")
    print(f"Base de datos dice: ${total_gasto_global:,.0f} total")
    print(f"Diferencia: ${abs(550000 - total_gasto_global):,.0f}")
    print()

    if total_gasto_global != 550000:
        print("❌ INCONSISTENCIA DETECTADA")
        print()

        if total_gasto_global < 550000:
            print(f"⚠️  Faltan ${550000 - total_gasto_global:,.0f} en la base de datos")
            print("   Posibles causas:")
            print("   - Servicios no importados del CSV")
            print("   - Servicios con otro nombre de cliente en CSV")
            print("   - Error en la importación")
        else:
            print(f"⚠️  Sobran ${total_gasto_global - 550000:,.0f} en la base de datos")
            print("   Posibles causas:")
            print("   - Servicios duplicados")
            print("   - Error en la segmentación")
    else:
        print("✅ DATOS CONSISTENTES")

    print("=" * 80)

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
