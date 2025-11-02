#!/usr/bin/env python3
"""
Script para analizar los 14 clientes del segmento custom_filter
Verifica consistencia entre datos actuales e históricos
"""
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

# Lista de los 14 clientes a analizar (según la imagen)
CLIENTES_SEGMENTO = [
    {
        'numero': 1,
        'nombre_segmento': 'Carmen Perez Meyer',
        'telefono': '+56984323068',
        'gasto_actual_esperado': 1240000,
        'gasto_historico_esperado': 2073000,
        'gasto_total_esperado': 3313000
    },
    {
        'numero': 2,
        'nombre_segmento': 'Alfredo Becerra',
        'telefono': '+56989586830',
        'gasto_actual_esperado': 605000,
        'gasto_historico_esperado': 2395000,
        'gasto_total_esperado': 3000000
    },
    {
        'numero': 3,
        'nombre_segmento': 'Automotriz Servimaq',
        'telefono': '+56996946226',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1780000,
        'gasto_total_esperado': 1780000
    },
    {
        'numero': 4,
        'nombre_segmento': 'Camilo Muñoz Hermosilla',
        'telefono': '+56966621983',
        'gasto_actual_esperado': 1698000,
        'gasto_historico_esperado': 0,
        'gasto_total_esperado': 1698000
    },
    {
        'numero': 5,
        'nombre_segmento': 'colegio adventista',
        'telefono': '+56941841101',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1280000,
        'gasto_total_esperado': 1280000
    },
    {
        'numero': 6,
        'nombre_segmento': 'Marcelo lopez vivar',
        'telefono': '+56940488641',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1275000,
        'gasto_total_esperado': 1275000
    },
    {
        'numero': 7,
        'nombre_segmento': 'Jose Luis Pardo Millacura',
        'telefono': '+56942182326',
        'gasto_actual_esperado': 130000,
        'gasto_historico_esperado': 1040000,
        'gasto_total_esperado': 1170000
    },
    {
        'numero': 8,
        'nombre_segmento': 'Ximena Schnettler Weisser',
        'telefono': '+56994545296',
        'gasto_actual_esperado': 40000,
        'gasto_historico_esperado': 1090000,
        'gasto_total_esperado': 1130000
    },
    {
        'numero': 9,
        'nombre_segmento': 'Guillermo Roa Urzua',
        'telefono': '+56966072696',
        'gasto_actual_esperado': 430000,
        'gasto_historico_esperado': 685000,
        'gasto_total_esperado': 1115000
    },
    {
        'numero': 10,
        'nombre_segmento': 'Marianela Noriega Pons',
        'telefono': '+56969654735',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1050000,
        'gasto_total_esperado': 1050000
    },
    {
        'numero': 11,
        'nombre_segmento': 'Gladis barrios Rodriguez',
        'telefono': '+56941849072',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1042000,
        'gasto_total_esperado': 1042000
    },
    {
        'numero': 12,
        'nombre_segmento': 'Lelikelen Centro de Yoga',
        'telefono': '+56975365827',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1040000,
        'gasto_total_esperado': 1040000
    },
    {
        'numero': 13,
        'nombre_segmento': 'Cristobal Urrutia',
        'telefono': '+56989693680',
        'gasto_actual_esperado': 836000,
        'gasto_historico_esperado': 184000,
        'gasto_total_esperado': 1020000
    },
    {
        'numero': 14,
        'nombre_segmento': 'Claudio Carmona Fernandini',
        'telefono': '+56932409471',
        'gasto_actual_esperado': 0,
        'gasto_historico_esperado': 1005000,
        'gasto_total_esperado': 1005000
    }
]

def analizar_cliente(cur, cliente_data):
    """Analiza un cliente específico y devuelve todos los detalles"""
    telefono = cliente_data['telefono']

    resultado = {
        'numero': cliente_data['numero'],
        'nombre_segmento': cliente_data['nombre_segmento'],
        'telefono': telefono,
        'esperado': cliente_data,
        'clientes_encontrados': [],
        'inconsistencias': [],
        'advertencias': []
    }

    # 1. Buscar TODOS los clientes con este teléfono en ventas_cliente
    cur.execute('''
        SELECT id, nombre, email, documento_identidad, pais, comuna_id, created_at
        FROM ventas_cliente
        WHERE telefono = %s
        ORDER BY id
    ''', (telefono,))

    clientes = cur.fetchall()

    if not clientes:
        resultado['inconsistencias'].append(f"❌ NO SE ENCONTRÓ ningún cliente con teléfono {telefono}")
        return resultado

    if len(clientes) > 1:
        resultado['advertencias'].append(f"⚠️  DUPLICADO: {len(clientes)} clientes con el mismo teléfono")

    # 2. Por cada cliente encontrado, obtener servicios históricos y calcular totales
    total_historico_real = 0
    total_actual_real = 0

    for cliente in clientes:
        cliente_id, nombre_bd, email, doc, pais, comuna_id, created = cliente

        # Servicios históricos
        cur.execute('''
            SELECT
                COUNT(*) as num_servicios,
                COALESCE(SUM(price_paid), 0) as total_gastado,
                MIN(service_date) as primera_compra,
                MAX(service_date) as ultima_compra
            FROM crm_service_history
            WHERE cliente_id = %s
        ''', (cliente_id,))

        hist = cur.fetchone()
        num_servicios_hist, gasto_hist, primera_hist, ultima_hist = hist

        # Últimos 5 servicios históricos
        cur.execute('''
            SELECT service_type, service_name, service_date, price_paid, reserva_id
            FROM crm_service_history
            WHERE cliente_id = %s
            ORDER BY service_date DESC
            LIMIT 5
        ''', (cliente_id,))

        servicios_hist = cur.fetchall()

        total_historico_real += float(gasto_hist)

        cliente_info = {
            'id': cliente_id,
            'nombre_bd': nombre_bd,
            'email': email,
            'documento': doc,
            'servicios_historicos': {
                'cantidad': num_servicios_hist,
                'total': float(gasto_hist),
                'primera_compra': str(primera_hist) if primera_hist else None,
                'ultima_compra': str(ultima_hist) if ultima_hist else None,
                'ultimos_5': [
                    {
                        'tipo': s[0],
                        'nombre': s[1],
                        'fecha': str(s[2]),
                        'precio': float(s[3]),
                        'reserva': s[4]
                    } for s in servicios_hist
                ]
            }
        }

        resultado['clientes_encontrados'].append(cliente_info)

    # 3. Comparar totales
    resultado['totales_reales'] = {
        'historico': total_historico_real,
        'actual': total_actual_real,  # Por ahora 0, necesitamos definir qué es "actual"
        'total': total_historico_real + total_actual_real
    }

    # 4. Detectar inconsistencias en montos
    diff_historico = abs(total_historico_real - cliente_data['gasto_historico_esperado'])
    if diff_historico > 1000:  # Tolerancia de $1,000
        resultado['inconsistencias'].append(
            f"❌ HISTÓRICO: Esperado ${cliente_data['gasto_historico_esperado']:,} pero encontrado ${total_historico_real:,.0f} (diferencia: ${diff_historico:,.0f})"
        )

    # 5. Verificar nombre
    nombres_bd = [c['nombre_bd'] for c in resultado['clientes_encontrados']]
    if cliente_data['nombre_segmento'] not in nombres_bd:
        resultado['advertencias'].append(
            f"⚠️  NOMBRE DIFERENTE: Segmento='{cliente_data['nombre_segmento']}' vs BD={nombres_bd}"
        )

    return resultado

def main():
    print("=" * 100)
    print("🔍 ANÁLISIS DE CONSISTENCIA: TOP 14 CLIENTES DEL SEGMENTO")
    print("=" * 100)
    print()

    conn = psycopg2.connect(os.getenv('DATABASE_URL'))
    cur = conn.cursor()

    resultados = []

    for cliente_data in CLIENTES_SEGMENTO:
        print(f"\n{'=' * 100}")
        print(f"#{cliente_data['numero']}. {cliente_data['nombre_segmento']} - {cliente_data['telefono']}")
        print(f"{'=' * 100}")

        resultado = analizar_cliente(cur, cliente_data)
        resultados.append(resultado)

        # Mostrar clientes encontrados
        if resultado['clientes_encontrados']:
            print(f"\n📋 CLIENTES EN BD: {len(resultado['clientes_encontrados'])}")
            for c in resultado['clientes_encontrados']:
                print(f"\n   ID: {c['id']}")
                print(f"   Nombre: {c['nombre_bd']}")
                print(f"   Email: {c['email']}")
                print(f"   Documento: {c['documento']}")
                print(f"\n   📊 Servicios Históricos:")
                print(f"      Cantidad: {c['servicios_historicos']['cantidad']}")
                print(f"      Total: ${c['servicios_historicos']['total']:,.0f}")
                print(f"      Primera compra: {c['servicios_historicos']['primera_compra']}")
                print(f"      Última compra: {c['servicios_historicos']['ultima_compra']}")

                if c['servicios_historicos']['ultimos_5']:
                    print(f"\n      Últimos 5 servicios:")
                    for s in c['servicios_historicos']['ultimos_5']:
                        print(f"         - {s['fecha']}: {s['tipo']} - {s['nombre']} (${s['precio']:,.0f}) [Reserva: {s['reserva']}]")

        # Mostrar totales
        print(f"\n💰 COMPARACIÓN DE TOTALES:")
        print(f"   Esperado Histórico: ${cliente_data['gasto_historico_esperado']:,}")
        print(f"   Real Histórico:     ${resultado['totales_reales']['historico']:,.0f}")

        # Mostrar advertencias e inconsistencias
        if resultado['advertencias']:
            print(f"\n⚠️  ADVERTENCIAS:")
            for adv in resultado['advertencias']:
                print(f"   {adv}")

        if resultado['inconsistencias']:
            print(f"\n❌ INCONSISTENCIAS:")
            for inc in resultado['inconsistencias']:
                print(f"   {inc}")
        else:
            print(f"\n✅ DATOS CONSISTENTES")

    # RESUMEN FINAL
    print(f"\n\n{'=' * 100}")
    print("📊 RESUMEN FINAL")
    print(f"{'=' * 100}")

    total_con_problemas = 0
    total_con_advertencias = 0
    total_ok = 0

    for r in resultados:
        if r['inconsistencias']:
            total_con_problemas += 1
        elif r['advertencias']:
            total_con_advertencias += 1
        else:
            total_ok += 1

    print(f"\nTotal clientes analizados: 14")
    print(f"✅ Datos consistentes: {total_ok}")
    print(f"⚠️  Con advertencias: {total_con_advertencias}")
    print(f"❌ Con inconsistencias: {total_con_problemas}")

    if total_con_problemas > 0:
        print(f"\n{'=' * 100}")
        print("❌ CLIENTES CON INCONSISTENCIAS (REVISAR ANTES DE PREMIAR):")
        print(f"{'=' * 100}")
        for r in resultados:
            if r['inconsistencias']:
                print(f"\n#{r['numero']}. {r['nombre_segmento']} ({r['telefono']})")
                for inc in r['inconsistencias']:
                    print(f"   {inc}")

    if total_con_advertencias > 0:
        print(f"\n{'=' * 100}")
        print("⚠️  CLIENTES CON ADVERTENCIAS (VERIFICAR):")
        print(f"{'=' * 100}")
        for r in resultados:
            if r['advertencias'] and not r['inconsistencias']:
                print(f"\n#{r['numero']}. {r['nombre_segmento']} ({r['telefono']})")
                for adv in r['advertencias']:
                    print(f"   {adv}")

    print(f"\n{'=' * 100}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()
