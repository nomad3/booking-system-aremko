#!/usr/bin/env python3
"""
Script para importar servicios históricos con RECONEXIÓN AUTOMÁTICA
Continúa desde el último registro procesado si la conexión se pierde
"""
import csv
import os
import sys
import re
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError
import time

load_dotenv()

CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - Servicios Vendidos (1).csv"
DATABASE_URL = os.getenv('DATABASE_URL')
BATCH_SIZE = 500  # Lotes de 500 registros
MAX_RETRIES = 3   # Máximo 3 intentos de reconexión

def extraer_telefono_y_nombre(campo_cliente):
    """Extrae nombre y teléfono del campo cliente"""
    campo = ' '.join(campo_cliente.split())
    match = re.search(r'(.+?)\s+([\d\s]+)$', campo)

    if match:
        nombre = match.group(1).strip()
        telefono_raw = match.group(2).replace(' ', '')
        return nombre, telefono_raw

    return campo.strip(), None

def normalizar_telefono(telefono):
    """Normaliza teléfono a formato +56XXXXXXXXX"""
    if not telefono:
        return None

    telefono = str(telefono).strip().replace(' ', '')

    if telefono.startswith('+56'):
        return telefono
    if telefono.startswith('56') and len(telefono) >= 11:
        return f'+{telefono}'
    if len(telefono) == 9:
        return f'+56{telefono}'
    if len(telefono) == 8:
        return f'+569{telefono}'

    return None

def conectar_bd(intentos=MAX_RETRIES):
    """Conecta a la BD con reintentos"""
    for intento in range(1, intentos + 1):
        try:
            conn = psycopg2.connect(DATABASE_URL)
            return conn
        except OperationalError as e:
            if intento < intentos:
                print(f"   ⚠️  Error de conexión (intento {intento}/{intentos}). Reintentando en 5 segundos...")
                time.sleep(5)
            else:
                raise

def buscar_cliente_por_telefono(cur, telefono_norm):
    """Busca el cliente por teléfono normalizado"""
    cur.execute(
        "SELECT id, nombre, telefono FROM ventas_cliente WHERE telefono = %s",
        (telefono_norm,)
    )
    return cur.fetchone()

def buscar_cliente_por_nombre(cur, nombre):
    """Busca cliente por nombre"""
    nombre_clean = nombre.lower().strip()

    cur.execute(
        "SELECT id, nombre, telefono FROM ventas_cliente WHERE LOWER(nombre) = %s",
        (nombre_clean,)
    )
    result = cur.fetchone()
    if result:
        return result

    cur.execute(
        "SELECT id, nombre, telefono FROM ventas_cliente WHERE LOWER(nombre) LIKE %s LIMIT 1",
        (f'%{nombre_clean}%',)
    )
    return cur.fetchone()

def importar_servicios_con_reconexion():
    print("=" * 70)
    print("📊 IMPORTACIÓN DE SERVICIOS CON RECONEXIÓN AUTOMÁTICA")
    print("=" * 70)
    print()

    # Conectar
    conn = conectar_bd()
    cur = conn.cursor()

    # 1. Verificar servicios actuales
    print("📋 PASO 1: Verificando estado actual...")
    cur.execute("SELECT COUNT(*) FROM crm_service_history")
    count_actual = cur.fetchone()[0]
    print(f"   Servicios actuales en BD: {count_actual:,}")
    print()

    # 2. Procesar CSV
    print(f"📋 PASO 2: Procesando CSV desde inicio...")
    print(f"   Archivo: {CSV_FILE}")
    print()

    stats = {
        'total_csv': 0,
        'clientes_encontrados': 0,
        'clientes_no_encontrados': 0,
        'servicios_importados': 0,
        'servicios_duplicados': 0,
        'errores': 0,
        'por_telefono': 0,
        'por_nombre': 0,
        'fechas_vacias': 0,
        'categorias_vacias': 0,
        'reconexiones': 0
    }

    clientes_no_encontrados = []
    batch_count = 0
    lote_actual = 0

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, 1):
            stats['total_csv'] += 1

            try:
                # Extraer datos del CSV
                nombre_csv, telefono_csv = extraer_telefono_y_nombre(row['cliente'])
                servicio = row['servicio'].strip()
                cantidad = int(row['cantidad']) if row['cantidad'] else 1
                valor = float(row['valor']) if row['valor'] else 0
                reserva_id = row['reserva'].strip() if row['reserva'] else None
                checkin_raw = row['checkin'].strip() if row['checkin'] else None
                categoria = row['categoria'].strip() if row['categoria'] else None

                # MANEJO DE FECHAS VACÍAS
                if not checkin_raw or checkin_raw == '':
                    checkin = '2020-01-01'
                    stats['fechas_vacias'] += 1
                else:
                    checkin = checkin_raw

                # MANEJO DE CATEGORÍAS VACÍAS
                if not categoria or categoria == '':
                    categoria = 'Sin categoría'
                    stats['categorias_vacias'] += 1

                # Normalizar teléfono
                telefono_norm = normalizar_telefono(telefono_csv)

                # Buscar cliente
                cliente_id = None
                cliente_encontrado = None

                # Reconectar si es necesario
                retry_count = 0
                while retry_count < MAX_RETRIES:
                    try:
                        # 1. Buscar por teléfono
                        if telefono_norm:
                            cliente_encontrado = buscar_cliente_por_telefono(cur, telefono_norm)
                            if cliente_encontrado:
                                cliente_id = cliente_encontrado[0]
                                stats['por_telefono'] += 1

                        # 2. Si no encuentra por teléfono, buscar por nombre
                        if not cliente_id:
                            cliente_encontrado = buscar_cliente_por_nombre(cur, nombre_csv)
                            if cliente_encontrado:
                                cliente_id = cliente_encontrado[0]
                                stats['por_nombre'] += 1

                        if cliente_id:
                            # Cliente encontrado - verificar si ya existe el servicio
                            cur.execute('''
                                SELECT id FROM crm_service_history
                                WHERE cliente_id = %s AND reserva_id = %s AND service_name = %s
                            ''', (cliente_id, reserva_id, servicio))

                            if cur.fetchone():
                                # Ya existe, saltar
                                stats['servicios_duplicados'] += 1
                            else:
                                # Insertar servicio
                                cur.execute('''
                                    INSERT INTO crm_service_history
                                    (cliente_id, reserva_id, service_type, service_name, service_date, quantity, price_paid)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                                ''', (cliente_id, reserva_id, categoria, servicio, checkin, cantidad, valor))

                                stats['servicios_importados'] += 1
                                batch_count += 1

                            stats['clientes_encontrados'] += 1
                        else:
                            # Cliente NO encontrado
                            stats['clientes_no_encontrados'] += 1
                            clientes_no_encontrados.append({
                                'nombre': nombre_csv,
                                'telefono_csv': telefono_csv,
                                'telefono_norm': telefono_norm,
                                'servicio': servicio
                            })

                        # COMMIT cada 500 registros NUEVOS
                        if batch_count >= BATCH_SIZE:
                            conn.commit()
                            lote_actual += 1
                            print(f"   ✅ Lote {lote_actual}: {batch_count} servicios guardados (Total nuevos: {stats['servicios_importados']:,}, Duplicados: {stats['servicios_duplicados']:,})")
                            batch_count = 0

                        break  # Si llegó aquí, todo OK, salir del retry loop

                    except OperationalError as e:
                        if 'SSL' in str(e) or 'closed' in str(e):
                            retry_count += 1
                            stats['reconexiones'] += 1
                            print(f"   ⚠️  Conexión perdida en fila {idx}. Reconectando (intento {retry_count}/{MAX_RETRIES})...")

                            try:
                                conn.close()
                            except:
                                pass

                            conn = conectar_bd()
                            cur = conn.cursor()

                            if retry_count >= MAX_RETRIES:
                                raise Exception(f"No se pudo reconectar después de {MAX_RETRIES} intentos")
                        else:
                            raise

            except Exception as e:
                stats['errores'] += 1
                print(f"   ❌ Error en fila {idx}: {e}")

    # COMMIT final de registros restantes
    if batch_count > 0:
        conn.commit()
        lote_actual += 1
        print(f"   ✅ Lote {lote_actual} (final): {batch_count} servicios guardados")

    print()
    print("💾 Todos los lotes guardados exitosamente")
    print()

    # 3. REPORTE FINAL
    print("=" * 70)
    print("📊 RESULTADOS FINALES")
    print("=" * 70)
    print()

    print(f"Total servicios en CSV: {stats['total_csv']:,}")
    print(f"✅ Servicios NUEVOS importados: {stats['servicios_importados']:,}")
    print(f"⏭️  Servicios duplicados (omitidos): {stats['servicios_duplicados']:,}")
    print()
    print(f"📞 Clientes procesados: {stats['clientes_encontrados']:,}")
    print(f"   - Por teléfono: {stats['por_telefono']:,} ({(stats['por_telefono']/stats['clientes_encontrados']*100) if stats['clientes_encontrados'] > 0 else 0:.1f}%)")
    print(f"   - Por nombre: {stats['por_nombre']:,} ({(stats['por_nombre']/stats['clientes_encontrados']*100) if stats['clientes_encontrados'] > 0 else 0:.1f}%)")
    print(f"❌ Clientes NO encontrados: {stats['clientes_no_encontrados']:,}")
    print()
    print(f"📅 Servicios sin fecha (usaron 2020-01-01): {stats['fechas_vacias']:,}")
    print(f"🏷️  Servicios sin categoría (usaron 'Sin categoría'): {stats['categorias_vacias']:,}")
    print(f"🔄 Reconexiones exitosas: {stats['reconexiones']}")
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
            print()

    # Verificación final
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
        importar_servicios_con_reconexion()
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
