#!/usr/bin/env python3
"""
Script para importar TODOS los servicios históricos desde CSV completo
Conecta servicios con clientes existentes usando el teléfono
"""
import csv
import os
import sys
import re
from datetime import datetime
from dotenv import load_dotenv
import psycopg2

load_dotenv()

CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - Servicios Vendidos (1).csv"
DATABASE_URL = os.getenv('DATABASE_URL')

def extraer_telefono_y_nombre(campo_cliente):
    """
    Extrae nombre y teléfono del campo cliente
    Ejemplos:
    - "Francisca Reyes 9340 8233" -> ("Francisca Reyes", "93408233")
    - "Mario zerega 989022916" -> ("Mario zerega", "989022916")
    """
    # Remover espacios múltiples
    campo = ' '.join(campo_cliente.split())

    # Buscar todos los dígitos al final (puede tener espacios)
    match = re.search(r'(.+?)\s+([\d\s]+)$', campo)

    if match:
        nombre = match.group(1).strip()
        telefono_raw = match.group(2).replace(' ', '')  # Remover espacios
        return nombre, telefono_raw

    # Si no encuentra patrón, retornar todo como nombre
    return campo.strip(), None

def normalizar_telefono(telefono):
    """Normaliza teléfono a formato +56XXXXXXXXX"""
    if not telefono:
        return None

    telefono = str(telefono).strip().replace(' ', '')

    # Ya tiene +56
    if telefono.startswith('+56'):
        return telefono

    # Tiene 56 al inicio
    if telefono.startswith('56') and len(telefono) >= 11:
        return f'+{telefono}'

    # Es un número de 9 dígitos
    if len(telefono) == 9:
        return f'+56{telefono}'

    # Es un número de 8 dígitos (agregar 9 al inicio)
    if len(telefono) == 8:
        return f'+569{telefono}'

    return None

def buscar_cliente_por_telefono(cur, telefono_norm):
    """Busca el cliente por teléfono normalizado"""
    cur.execute(
        "SELECT id, nombre, telefono FROM ventas_cliente WHERE telefono = %s",
        (telefono_norm,)
    )
    return cur.fetchone()

def buscar_cliente_por_nombre(cur, nombre):
    """Busca cliente por nombre (coincidencia parcial)"""
    nombre_clean = nombre.lower().strip()

    # Buscar coincidencia exacta
    cur.execute(
        "SELECT id, nombre, telefono FROM ventas_cliente WHERE LOWER(nombre) = %s",
        (nombre_clean,)
    )
    result = cur.fetchone()
    if result:
        return result

    # Buscar coincidencia parcial (LIKE)
    cur.execute(
        "SELECT id, nombre, telefono FROM ventas_cliente WHERE LOWER(nombre) LIKE %s LIMIT 1",
        (f'%{nombre_clean}%',)
    )
    return cur.fetchone()

def importar_servicios_completo():
    print("=" * 70)
    print("📊 IMPORTACIÓN COMPLETA DE SERVICIOS HISTÓRICOS")
    print("=" * 70)
    print()

    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    conn.autocommit = False

    # 1. LIMPIAR servicios actuales (de la prueba)
    print("🗑️  PASO 1: Limpiando servicios de prueba...")
    cur.execute("SELECT COUNT(*) FROM crm_service_history")
    count_antes = cur.fetchone()[0]
    print(f"   Servicios actuales: {count_antes:,}")

    if count_antes > 0:
        cur.execute("DELETE FROM crm_service_history")
        conn.commit()
        print(f"   ✅ {count_antes:,} servicios borrados")
    print()

    # 2. ANALIZAR CSV
    print("📋 PASO 2: Procesando CSV completo...")
    print(f"   Archivo: {CSV_FILE}")
    print()

    stats = {
        'total_csv': 0,
        'clientes_encontrados': 0,
        'clientes_no_encontrados': 0,
        'servicios_importados': 0,
        'errores': 0,
        'por_telefono': 0,
        'por_nombre': 0
    }

    clientes_no_encontrados = []

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, 1):
            stats['total_csv'] += 1

            # Reporte de progreso cada 1000 registros
            if idx % 1000 == 0:
                print(f"   Procesados: {idx:,} / ~29,677 ({(idx/29677)*100:.1f}%)")

            try:
                # Extraer datos del CSV
                nombre_csv, telefono_csv = extraer_telefono_y_nombre(row['cliente'])
                servicio = row['servicio'].strip()
                cantidad = int(row['cantidad']) if row['cantidad'] else 1
                valor = float(row['valor']) if row['valor'] else 0
                reserva_id = row['reserva'].strip() if row['reserva'] else None
                checkin = row['checkin'].strip() if row['checkin'] else None
                categoria = row['categoria'].strip() if row['categoria'] else None

                # Normalizar teléfono
                telefono_norm = normalizar_telefono(telefono_csv)

                # Buscar cliente
                cliente_id = None
                cliente_encontrado = None
                metodo_busqueda = None

                # 1. Buscar por teléfono
                if telefono_norm:
                    cliente_encontrado = buscar_cliente_por_telefono(cur, telefono_norm)
                    if cliente_encontrado:
                        cliente_id = cliente_encontrado[0]
                        metodo_busqueda = 'teléfono'
                        stats['por_telefono'] += 1

                # 2. Si no encuentra por teléfono, buscar por nombre
                if not cliente_id:
                    cliente_encontrado = buscar_cliente_por_nombre(cur, nombre_csv)
                    if cliente_encontrado:
                        cliente_id = cliente_encontrado[0]
                        metodo_busqueda = 'nombre'
                        stats['por_nombre'] += 1

                if cliente_id:
                    # Cliente encontrado - importar servicio
                    stats['clientes_encontrados'] += 1

                    # Insertar servicio
                    cur.execute('''
                        INSERT INTO crm_service_history
                        (cliente_id, reserva_id, service_type, service_name, service_date, quantity, price_paid)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ''', (cliente_id, reserva_id, categoria, servicio, checkin, cantidad, valor))

                    stats['servicios_importados'] += 1

                else:
                    # Cliente NO encontrado
                    stats['clientes_no_encontrados'] += 1
                    clientes_no_encontrados.append({
                        'nombre': nombre_csv,
                        'telefono_csv': telefono_csv,
                        'telefono_norm': telefono_norm,
                        'servicio': servicio
                    })

            except Exception as e:
                stats['errores'] += 1
                print(f"❌ Error en fila {idx}: {e}")

    # COMMIT
    print()
    print("💾 Guardando datos...")
    conn.commit()
    print("✅ COMMIT exitoso")
    print()

    # 3. REPORTE FINAL
    print("=" * 70)
    print("📊 RESULTADOS FINALES")
    print("=" * 70)
    print()

    print(f"Total servicios en CSV: {stats['total_csv']:,}")
    print(f"✅ Clientes encontrados: {stats['clientes_encontrados']:,}")
    print(f"   - Por teléfono: {stats['por_telefono']:,} ({(stats['por_telefono']/stats['clientes_encontrados']*100):.1f}%)")
    print(f"   - Por nombre: {stats['por_nombre']:,} ({(stats['por_nombre']/stats['clientes_encontrados']*100):.1f}%)")
    print(f"❌ Clientes NO encontrados: {stats['clientes_no_encontrados']:,}")
    print(f"📦 Servicios importados: {stats['servicios_importados']:,}")
    print(f"⚠️  Errores: {stats['errores']}")
    print()

    if clientes_no_encontrados:
        print("=" * 70)
        print(f"❌ CLIENTES NO ENCONTRADOS (primeros 20 de {len(clientes_no_encontrados):,})")
        print("=" * 70)
        for i, c in enumerate(clientes_no_encontrados[:20], 1):
            print(f"{i}. {c['nombre']}")
            print(f"   Teléfono CSV: {c['telefono_csv']}")
            print(f"   Teléfono normalizado: {c['telefono_norm']}")
            print(f"   Servicio: {c['servicio']}")
            print()

    # Verificar cantidad final en BD
    print("=" * 70)
    print("📋 VERIFICACIÓN FINAL")
    print("=" * 70)
    cur.execute("SELECT COUNT(*) FROM crm_service_history")
    count_final = cur.fetchone()[0]
    print(f"Total servicios en BD: {count_final:,}")
    print()

    print("=" * 70)

    cur.close()
    conn.close()

if __name__ == '__main__':
    try:
        importar_servicios_completo()
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
