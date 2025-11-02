#!/usr/bin/env python3
"""
Script de importación de 13,294 clientes antiguos a PRODUCCIÓN
Conexión directa a PostgreSQL en Render
"""
import csv
import os
import sys
from datetime import datetime
from collections import defaultdict
import psycopg2
from psycopg2 import sql
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Archivo CSV a importar
CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - 13294 clientes (1).csv"

# Configuración de base de datos (Render)
DATABASE_URL = os.getenv('DATABASE_URL')

if not DATABASE_URL:
    print("❌ ERROR: DATABASE_URL no encontrada en variables de entorno")
    print("Asegúrate de que el archivo .env existe y contiene DATABASE_URL")
    print("\nPuedes crear el archivo .env con:")
    print("DATABASE_URL=postgresql://usuario:password@host:puerto/database")
    sys.exit(1)

# Mapeo de comunas CSV → comunas BD
# Este mapeo ayuda a normalizar las variantes más comunes
MAPEO_COMUNAS = {
    # Puerto Montt variantes
    'puerto montt': 'Puerto Montt',
    'pto montt': 'Puerto Montt',
    'puerto montt, los lagos': 'Puerto Montt',
    'puerto montt, lagos': 'Puerto Montt',
    'puerto montt, región de los lagos': 'Puerto Montt',

    # Puerto Varas variantes
    'puerto varas': 'Puerto Varas',
    'pto varas': 'Puerto Varas',
    'puerto varas, los lagos': 'Puerto Varas',
    'puerto varas, lagos': 'Puerto Varas',

    # Santiago variantes
    'santiago': 'Santiago',
    'santiago, metropolitana': 'Santiago',
    'santiago, rm': 'Santiago',
    'santiago, región metropolitana': 'Santiago',
    'santiago, los lagos': 'Santiago',  # Error en datos

    # Osorno variantes
    'osorno': 'Osorno',
    'osorno, los lagos': 'Osorno',
    'osorno, lagos': 'Osorno',

    # Otras comunas
    'llanquihue': 'Llanquihue',
    'llanquihue, los lagos': 'Llanquihue',
    'llanquihue, lagos': 'Llanquihue',

    'frutillar': 'Frutillar',
    'frutillar, los lagos': 'Frutillar',

    'calbuco': 'Calbuco',
    'calbuco, los lagos': 'Calbuco',

    'valdivia': 'Valdivia',
    'valdivia, los rios': 'Valdivia',
    'valdivia, los ríos': 'Valdivia',

    'temuco': 'Temuco',
    'temuco, araucanía': 'Temuco',

    'concepción': 'Concepción',
    'concepcion': 'Concepción',

    'viña del mar': 'Viña del Mar',
    'vina del mar': 'Viña del Mar',
    'viña del mar, valparaiso': 'Viña del Mar',
    'viña del mar, valparaíso': 'Viña del Mar',

    'valparaíso': 'Valparaíso',
    'valparaiso': 'Valparaíso',

    # Casos especiales
    'resto chile': None,
    'chiloe, resto chile': 'Castro',  # Asumir Castro como capital de Chiloé
}

def normalizar_telefono(telefono):
    """Normaliza teléfono agregando +56"""
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
    """Limpia y normaliza el texto de comuna"""
    if not comuna:
        return None

    # Remover comillas y espacios
    comuna = str(comuna).strip().strip('"').strip().lower()

    # Buscar en mapeo
    return MAPEO_COMUNAS.get(comuna, comuna.title())

def get_comuna_id(cursor, comuna_nombre):
    """Obtiene el ID de la comuna desde la BD"""
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

def importar_clientes(dry_run=True):
    """
    Importa clientes a producción

    Args:
        dry_run: Si es True, solo simula la importación sin guardar
    """
    modo = "🔍 DRY-RUN (SIMULACIÓN)" if dry_run else "🚀 MODO REAL"

    print("=" * 70)
    print(f"📊 IMPORTACIÓN DE CLIENTES A PRODUCCIÓN - {modo}")
    print("=" * 70)
    print()

    if not dry_run:
        print("⚠️  ADVERTENCIA: Modo REAL activado")
        print("   Los datos SE GUARDARÁN en la base de datos de producción")
        print("   ✅ Confirmación recibida vía --confirm flag")
        print()

    print(f"📁 Archivo CSV: {CSV_FILE}")
    print(f"🔌 Conectando a base de datos de producción...")

    # Conectar a BD
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        print("✅ Conexión exitosa a PostgreSQL en Render")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return

    print()
    print("📊 Obteniendo datos actuales de la BD...")

    # Obtener teléfonos existentes
    cursor.execute("SELECT telefono FROM ventas_cliente")
    telefonos_existentes = set(row[0] for row in cursor.fetchall())
    print(f"   Clientes actuales en BD: {len(telefonos_existentes):,}")

    # Obtener mapeo de comunas
    cursor.execute("SELECT id, nombre FROM ventas_comuna")
    comunas_bd = {row[1].lower(): row[0] for row in cursor.fetchall()}
    print(f"   Comunas disponibles en BD: {len(comunas_bd):,}")

    print()
    print("🔍 Procesando archivo CSV...")
    print()

    # Estadísticas
    stats = {
        'total_csv': 0,
        'duplicados_csv': 0,
        'ya_existe_bd': 0,
        'importados': 0,
        'errores': 0,
        'comunas_normalizadas': 0,
        'comunas_sin_normalizar': 0,
        'sin_comuna': 0
    }

    # Logs
    importados_log = []
    duplicados_log = []
    errores_log = []

    # Procesar CSV
    telefonos_vistos = set()

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader, 1):
            stats['total_csv'] += 1

            try:
                # Normalizar teléfono
                telefono_orig = row['Telefono']
                telefono_norm = normalizar_telefono(telefono_orig)

                if not telefono_norm:
                    stats['errores'] += 1
                    errores_log.append({
                        'linea': idx,
                        'error': 'Teléfono inválido',
                        'telefono': telefono_orig,
                        'nombre': row['nombre']
                    })
                    continue

                # Verificar duplicados en CSV
                if telefono_norm in telefonos_vistos:
                    stats['duplicados_csv'] += 1
                    duplicados_log.append({
                        'telefono': telefono_norm,
                        'nombre': row['nombre']
                    })
                    continue

                telefonos_vistos.add(telefono_norm)

                # Verificar si ya existe en BD
                if telefono_norm in telefonos_existentes:
                    stats['ya_existe_bd'] += 1
                    duplicados_log.append({
                        'telefono': telefono_norm,
                        'nombre': row['nombre'],
                        'razon': 'Ya existe en BD'
                    })
                    continue

                # Preparar datos del cliente
                nombre = row['nombre'].strip()
                email = row['Email'].strip() if row['Email'] else None
                documento = row['documento_identidad'].strip() if row['documento_identidad'] else None
                pais = row['pais'].strip() if row['pais'] else None
                fecha_creacion = row['Fecha_creacion'] if row['Fecha_creacion'] else None

                # Normalizar comuna
                comuna_csv = row['comuna']
                comuna_id = None

                if comuna_csv:
                    comuna_norm = normalizar_comuna_texto(comuna_csv)
                    if comuna_norm:
                        comuna_id = get_comuna_id(cursor, comuna_norm)
                        if comuna_id:
                            stats['comunas_normalizadas'] += 1
                        else:
                            stats['comunas_sin_normalizar'] += 1
                else:
                    stats['sin_comuna'] += 1

                # Importar (solo si no es dry-run)
                if not dry_run:
                    try:
                        cursor.execute("""
                            INSERT INTO ventas_cliente
                            (nombre, email, telefono, documento_identidad, pais, comuna_id, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """, (nombre, email, telefono_norm, documento, pais, comuna_id, fecha_creacion))
                    except Exception as e:
                        stats['errores'] += 1
                        errores_log.append({
                            'linea': idx,
                            'error': str(e),
                            'telefono': telefono_norm,
                            'nombre': nombre
                        })
                        continue

                stats['importados'] += 1
                importados_log.append({
                    'telefono': telefono_norm,
                    'nombre': nombre,
                    'comuna_id': comuna_id
                })

                # Progress indicator
                if idx % 500 == 0:
                    print(f"   ⏳ Procesados {idx:,}/{stats['total_csv']:,} registros...")

            except Exception as e:
                stats['errores'] += 1
                errores_log.append({
                    'linea': idx,
                    'error': str(e),
                    'datos': row
                })

    # Commit o rollback
    if not dry_run:
        if stats['errores'] == 0:
            conn.commit()
            print()
            print("✅ Transacción confirmada (COMMIT)")
        else:
            conn.rollback()
            print()
            print("⚠️  Transacción revertida (ROLLBACK) debido a errores")

    print()
    print("=" * 70)
    print("📋 REPORTE FINAL")
    print("=" * 70)
    print()

    print("📊 TOTALES:")
    print(f"   Total registros en CSV: {stats['total_csv']:,}")
    print(f"   ✅ Importados exitosamente: {stats['importados']:,}")
    print(f"   ⏭️  Duplicados en CSV (skip): {stats['duplicados_csv']:,}")
    print(f"   ⏭️  Ya existían en BD (skip): {stats['ya_existe_bd']:,}")
    print(f"   ❌ Errores: {stats['errores']:,}")
    print()

    print("📍 COMUNAS:")
    print(f"   ✅ Normalizadas con éxito: {stats['comunas_normalizadas']:,}")
    print(f"   ⚠️  Sin normalizar (NULL): {stats['comunas_sin_normalizar']:,}")
    print(f"   ℹ️  Sin comuna en CSV: {stats['sin_comuna']:,}")
    print()

    if errores_log[:5]:
        print("❌ Primeros errores:")
        for err in errores_log[:5]:
            print(f"   Línea {err.get('linea', '?')}: {err['error']}")
        if len(errores_log) > 5:
            print(f"   ... y {len(errores_log) - 5} errores más")
        print()

    # Guardar logs
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    if not dry_run and stats['importados'] > 0:
        log_file = f'logs/import_clientes_{timestamp}.log'
        os.makedirs('logs', exist_ok=True)

        with open(log_file, 'w', encoding='utf-8') as f:
            f.write(f"Importación realizada: {timestamp}\n")
            f.write(f"Total importados: {stats['importados']}\n")
            f.write(f"Total errores: {stats['errores']}\n\n")

            f.write("=== CLIENTES IMPORTADOS ===\n")
            for cliente in importados_log[:100]:
                f.write(f"{cliente['telefono']}: {cliente['nombre']}\n")

            if errores_log:
                f.write("\n=== ERRORES ===\n")
                for err in errores_log:
                    f.write(f"Línea {err.get('linea', '?')}: {err}\n")

        print(f"💾 Log guardado en: {log_file}")
        print()

    print("=" * 70)
    if dry_run:
        print("✅ SIMULACIÓN COMPLETADA")
        print()
        print("📋 SIGUIENTE PASO:")
        print("   Para importar realmente, ejecuta:")
        print("   python3 scripts/importar_clientes_produccion.py --confirm")
    else:
        print("✅ IMPORTACIÓN COMPLETADA")
        print(f"   {stats['importados']:,} clientes agregados a producción")
    print("=" * 70)

    cursor.close()
    conn.close()

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Importar clientes históricos a producción')
    parser.add_argument('--confirm', action='store_true',
                       help='Ejecutar importación REAL (sin este flag, solo simula)')

    args = parser.parse_args()

    try:
        importar_clientes(dry_run=not args.confirm)
    except KeyboardInterrupt:
        print("\n\n⚠️  Importación interrumpida por el usuario")
    except Exception as e:
        print(f"\n❌ ERROR FATAL: {e}")
        import traceback
        traceback.print_exc()
