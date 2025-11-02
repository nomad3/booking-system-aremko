#!/usr/bin/env python3
"""
Script OPTIMIZADO para importar solo registros con documento_identidad > 50 caracteres
Procesa solo los ~500 registros que fallaron anteriormente
"""
import csv
import os
import sys
from dotenv import load_dotenv
import psycopg2

# Deshabilitar buffering
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Cargar variables de entorno
load_dotenv()

# Archivo CSV
CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - 13294 clientes (1).csv"

# Configuración de BD
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

def importar_documentos_largos():
    print("=" * 70, flush=True)
    print("📊 IMPORTACIÓN DE CLIENTES CON DOCUMENTOS LARGOS (>50 CHARS)", flush=True)
    print("=" * 70, flush=True)
    print(f"📁 CSV: {CSV_FILE}", flush=True)
    print(flush=True)

    # Conectar
    print("🔌 Conectando a PostgreSQL...", flush=True)
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
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
        'con_doc_largo': 0,
        'total_importados': 0,
        'total_skipped': 0,
        'total_errores': 0,
    }

    # Leer CSV y filtrar solo documentos > 50 caracteres
    print("🔄 Filtrando registros con documento > 50 caracteres...", flush=True)
    print(flush=True)

    registros_a_importar = []

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, 1):
            stats['total_procesados'] += 1

            try:
                # Verificar si tiene documento largo
                documento = row['documento_identidad'].strip() if row['documento_identidad'] else None

                # FILTRO: Solo procesar si documento > 50 caracteres
                if not documento or len(documento) <= 50:
                    continue

                stats['con_doc_largo'] += 1

                # Normalizar teléfono
                telefono_norm = normalizar_telefono(row['Telefono'])
                if not telefono_norm or telefono_norm in telefonos_existentes:
                    stats['total_skipped'] += 1
                    continue

                # Preparar datos
                nombre = row['nombre'].strip()
                email = row['Email'].strip() if row['Email'] else None
                pais = row['pais'].strip() if row['pais'] else None
                fecha_creacion = row['Fecha_creacion'] if row['Fecha_creacion'] else None

                # Comuna
                comuna_id = None
                if row['comuna']:
                    comuna_norm = normalizar_comuna_texto(row['comuna'])
                    if comuna_norm:
                        comuna_id = get_comuna_id(cursor, comuna_norm)

                # Agregar a lista
                registros_a_importar.append((nombre, email, telefono_norm, documento, pais, comuna_id, fecha_creacion))

            except Exception as e:
                stats['total_errores'] += 1

    print(f"✅ Filtrado completado:", flush=True)
    print(f"   Total en CSV: {stats['total_procesados']:,}", flush=True)
    print(f"   Con documento > 50 chars: {stats['con_doc_largo']:,}", flush=True)
    print(f"   A importar (nuevos): {len(registros_a_importar):,}", flush=True)
    print(flush=True)

    # Importar todos de una vez (son pocos)
    if registros_a_importar:
        print(f"🔄 Importando {len(registros_a_importar):,} registros...", flush=True)
        try:
            cursor.executemany("""
                INSERT INTO ventas_cliente
                (nombre, email, telefono, documento_identidad, pais, comuna_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, registros_a_importar)

            conn.commit()
            stats['total_importados'] = len(registros_a_importar)
            print(f"✅ {stats['total_importados']:,} clientes importados exitosamente", flush=True)

        except Exception as e:
            conn.rollback()
            print(f"❌ Error en importación: {e}", flush=True)
            stats['total_errores'] = len(registros_a_importar)
    else:
        print("ℹ️  No hay registros nuevos para importar", flush=True)

    print(flush=True)
    print("=" * 70, flush=True)
    print("📋 REPORTE FINAL", flush=True)
    print("=" * 70, flush=True)
    print(f"Total procesados: {stats['total_procesados']:,}", flush=True)
    print(f"Con documento > 50 chars: {stats['con_doc_largo']:,}", flush=True)
    print(f"✅ Total importados: {stats['total_importados']:,}", flush=True)
    print(f"⏭️  Total skipped: {stats['total_skipped']:,}", flush=True)
    print(f"❌ Total errores: {stats['total_errores']:,}", flush=True)
    print("=" * 70, flush=True)

    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        importar_documentos_largos()
    except KeyboardInterrupt:
        print("\n⚠️  Importación interrumpida", flush=True)
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}", flush=True)
        import traceback
        traceback.print_exc()
