#!/usr/bin/env python3
"""
Script de importación de clientes en LOTES
Procesa 500 clientes a la vez con COMMIT incremental
"""
import csv
import os
import sys
from datetime import datetime
from collections import defaultdict
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Deshabilitar buffering de Python
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Cargar variables de entorno
load_dotenv()

# Archivo CSV a importar
CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - 13294 clientes (1).csv"

# Tamaño del lote
BATCH_SIZE = 500

# Configuración de base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no encontrada", flush=True)
    sys.exit(1)

# Mapeo de comunas
MAPEO_COMUNAS = {
    'puerto montt': 'Puerto Montt', 'pto montt': 'Puerto Montt',
    'puerto montt, los lagos': 'Puerto Montt', 'puerto montt, lagos': 'Puerto Montt',
    'puerto varas': 'Puerto Varas', 'pto varas': 'Puerto Varas',
    'santiago': 'Santiago', 'santiago, metropolitana': 'Santiago',
    'santiago, rm': 'Santiago', 'osorno': 'Osorno',
    'llanquihue': 'Llanquihue', 'frutillar': 'Frutillar',
    'calbuco': 'Calbuco', 'valdivia': 'Valdivia',
    'temuco': 'Temuco', 'concepción': 'Concepción',
    'concepcion': 'Concepción', 'viña del mar': 'Viña del Mar',
    'vina del mar': 'Viña del Mar', 'valparaíso': 'Valparaíso',
    'valparaiso': 'Valparaíso', 'resto chile': None,
}

def normalizar_telefono(telefono):
    if not telefono:
        return None
    telefono = str(telefono).strip()
    if telefono.startswith('+56'):
        return telefono
    if telefono.startswith('56') and len(telefono) >= 11:
        return f'+{telefono}'
    if len(telefono) == 9:
        return f'+56{telefono}'
    return None

def normalizar_comuna_texto(comuna):
    if not comuna:
        return None
    comuna = str(comuna).strip().strip('"').strip().lower()
    return MAPEO_COMUNAS.get(comuna, comuna.title())

def get_comuna_id(cursor, comuna_nombre):
    if not comuna_nombre:
        return None
    try:
        cursor.execute(
            "SELECT id FROM ventas_comuna WHERE LOWER(nombre) = LOWER(%s) LIMIT 1",
            (comuna_nombre,)
        )
        result = cursor.fetchone()
        return result[0] if result else None
    except:
        return None

def importar_por_lotes():
    print("=" * 70, flush=True)
    print("📊 IMPORTACIÓN DE CLIENTES POR LOTES", flush=True)
    print("=" * 70, flush=True)
    print(f"📁 CSV: {CSV_FILE}", flush=True)
    print(f"📦 Tamaño de lote: {BATCH_SIZE} registros", flush=True)
    print(flush=True)

    # Conectar
    print("🔌 Conectando a PostgreSQL...", flush=True)
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False  # Transacciones manuales
    cursor = conn.cursor()

    # Configurar timeout
    cursor.execute("SET statement_timeout = '60s'")
    conn.commit()

    print("✅ Conexión exitosa", flush=True)
    print(flush=True)

    # Obtener teléfonos existentes
    print("📊 Obteniendo clientes actuales...", flush=True)
    cursor.execute("SELECT telefono FROM ventas_cliente")
    telefonos_existentes = set(row[0] for row in cursor.fetchall())
    print(f"   Clientes actuales: {len(telefonos_existentes):,}", flush=True)
    print(flush=True)

    # Estadísticas
    stats = {
        'total_procesados': 0,
        'total_importados': 0,
        'total_skipped': 0,
        'total_errores': 0,
        'lotes_completados': 0
    }

    # Leer CSV y procesar en lotes
    print("🔄 Iniciando importación por lotes...", flush=True)
    print(flush=True)

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        lote_actual = []
        telefonos_vistos = set()

        for idx, row in enumerate(reader, 1):
            stats['total_procesados'] += 1

            try:
                # Normalizar teléfono
                telefono_norm = normalizar_telefono(row['Telefono'])
                if not telefono_norm or telefono_norm in telefonos_vistos or telefono_norm in telefonos_existentes:
                    stats['total_skipped'] += 1
                    continue

                telefonos_vistos.add(telefono_norm)

                # Preparar datos
                nombre = row['nombre'].strip()
                email = row['Email'].strip() if row['Email'] else None
                documento = row['documento_identidad'].strip() if row['documento_identidad'] else None
                pais = row['pais'].strip() if row['pais'] else None
                fecha_creacion = row['Fecha_creacion'] if row['Fecha_creacion'] else None

                # Comuna
                comuna_id = None
                if row['comuna']:
                    comuna_norm = normalizar_comuna_texto(row['comuna'])
                    if comuna_norm:
                        comuna_id = get_comuna_id(cursor, comuna_norm)

                # Agregar al lote
                lote_actual.append((nombre, email, telefono_norm, documento, pais, comuna_id, fecha_creacion))

                # Si el lote está lleno, insertar
                if len(lote_actual) >= BATCH_SIZE:
                    try:
                        # Insertar lote
                        cursor.executemany("""
                            INSERT INTO ventas_cliente
                            (nombre, email, telefono, documento_identidad, pais, comuna_id, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, lote_actual)

                        # COMMIT
                        conn.commit()

                        stats['total_importados'] += len(lote_actual)
                        stats['lotes_completados'] += 1

                        print(f"✅ Lote {stats['lotes_completados']}: {len(lote_actual)} clientes importados | Total: {stats['total_importados']:,}", flush=True)

                        # Reiniciar lote
                        lote_actual = []

                    except Exception as e:
                        conn.rollback()
                        print(f"❌ Error en lote {stats['lotes_completados']+1}: {e}", flush=True)
                        stats['total_errores'] += len(lote_actual)
                        lote_actual = []

            except Exception as e:
                stats['total_errores'] += 1

        # Procesar lote final
        if lote_actual:
            try:
                cursor.executemany("""
                    INSERT INTO ventas_cliente
                    (nombre, email, telefono, documento_identidad, pais, comuna_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, lote_actual)
                conn.commit()
                stats['total_importados'] += len(lote_actual)
                stats['lotes_completados'] += 1
                print(f"✅ Lote final: {len(lote_actual)} clientes importados", flush=True)
            except Exception as e:
                conn.rollback()
                print(f"❌ Error en lote final: {e}", flush=True)
                stats['total_errores'] += len(lote_actual)

    print(flush=True)
    print("=" * 70, flush=True)
    print("📋 REPORTE FINAL", flush=True)
    print("=" * 70, flush=True)
    print(f"Total procesados: {stats['total_procesados']:,}", flush=True)
    print(f"✅ Total importados: {stats['total_importados']:,}", flush=True)
    print(f"⏭️  Total skipped: {stats['total_skipped']:,}", flush=True)
    print(f"❌ Total errores: {stats['total_errores']:,}", flush=True)
    print(f"📦 Lotes completados: {stats['lotes_completados']}", flush=True)
    print("=" * 70, flush=True)

    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        importar_por_lotes()
    except KeyboardInterrupt:
        print("\n⚠️  Importación interrumpida", flush=True)
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}", flush=True)
        import traceback
        traceback.print_exc()
