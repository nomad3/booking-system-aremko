#!/usr/bin/env python3
"""
Script de análisis previo para importación de 13,294 clientes antiguos
Fase 1: Análisis sin modificar la base de datos
"""
import csv
import os
from collections import Counter, defaultdict
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor
from difflib import get_close_matches

# Cargar variables de entorno
load_dotenv()

# Archivo CSV a importar
CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - 13294 clientes (1).csv"

def get_db_connection():
    """Obtiene conexión a la base de datos de producción"""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise Exception("DATABASE_URL no encontrada en .env")
    return psycopg2.connect(database_url)

def normalizar_telefono(telefono):
    """
    Normaliza teléfono agregando +56 al inicio
    """
    if not telefono:
        return None

    telefono = str(telefono).strip()

    # Si ya tiene +56, retornar
    if telefono.startswith('+56'):
        return telefono

    # Si tiene 56 al inicio sin +, agregar +
    if telefono.startswith('56') and len(telefono) >= 11:
        return f'+{telefono}'

    # Si tiene 9 dígitos, agregar +56
    if len(telefono) == 9:
        return f'+56{telefono}'

    return None

def normalizar_comuna_texto(comuna):
    """
    Limpia y normaliza el texto de comuna
    """
    if not comuna:
        return None

    # Remover comillas
    comuna = str(comuna).strip().strip('"').strip()

    # Capitalizar cada palabra
    comuna = ' '.join(word.capitalize() for word in comuna.split())

    # Casos especiales
    especiales = {
        'Pto Montt': 'Puerto Montt',
        'Pto Varas': 'Puerto Varas',
        'Chiloe': 'Chiloé',
        'Concepcion': 'Concepción',
        'Valparaiso': 'Valparaíso',
        'Vina Del Mar': 'Viña del Mar',
        'Resto Chile': None,  # No es comuna específica
    }

    return especiales.get(comuna, comuna)

def analizar_csv():
    """
    Analiza el archivo CSV y retorna estadísticas
    """
    print("=" * 70)
    print("📊 FASE 1: ANÁLISIS PREVIO DE IMPORTACIÓN")
    print("=" * 70)
    print()

    print(f"📁 Archivo: {CSV_FILE}")
    print(f"🔌 Conectando a base de datos de producción...")

    # Conectar a BD
    conn = get_db_connection()
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    # Obtener todos los teléfonos actuales en BD
    cursor.execute("SELECT telefono FROM ventas_cliente")
    telefonos_bd = set(row['telefono'] for row in cursor.fetchall())
    print(f"✅ Clientes actuales en BD: {len(telefonos_bd):,}")
    print()

    # Obtener todas las comunas de BD
    cursor.execute("SELECT id, nombre FROM ventas_comuna ORDER BY nombre")
    comunas_bd = {row['nombre'].lower(): row for row in cursor.fetchall()}
    print(f"✅ Comunas disponibles en BD: {len(comunas_bd):,}")
    print()

    # Analizar CSV
    print("🔍 Analizando archivo CSV...")
    print()

    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        # Estadísticas
        total_registros = 0
        telefonos_csv = []
        emails_count = 0
        documentos_count = 0
        comunas_csv = []
        paises = Counter()

        # Análisis de duplicados
        telefonos_vistos = set()
        duplicados_en_csv = []
        ya_existe_en_bd = []
        nuevos_a_importar = []

        # Análisis de comunas
        comunas_counter = Counter()
        comuna_matches = defaultdict(list)

        # Datos sucios
        documentos_sucios = []

        for row in reader:
            total_registros += 1

            # Analizar teléfono
            telefono_orig = row['Telefono']
            telefono_norm = normalizar_telefono(telefono_orig)

            if telefono_norm:
                telefonos_csv.append(telefono_norm)

                # Detectar duplicados
                if telefono_norm in telefonos_vistos:
                    duplicados_en_csv.append((telefono_orig, row['nombre']))
                elif telefono_norm in telefonos_bd:
                    ya_existe_en_bd.append((telefono_norm, row['nombre']))
                else:
                    nuevos_a_importar.append((telefono_norm, row['nombre']))

                telefonos_vistos.add(telefono_norm)

            # Contar emails
            if row['Email']:
                emails_count += 1

            # Contar documentos
            documento = row['documento_identidad']
            if documento:
                documentos_count += 1
                # Detectar datos sucios
                if any(char.isalpha() for char in documento.lower()) and 'capuccino' in documento.lower():
                    documentos_sucios.append((documento, row['nombre']))

            # Analizar comunas
            comuna_orig = row['comuna']
            if comuna_orig:
                comuna_norm = normalizar_comuna_texto(comuna_orig)
                if comuna_norm:
                    comunas_csv.append(comuna_norm)
                    comunas_counter[comuna_norm] += 1

                    # Buscar match en BD
                    comuna_lower = comuna_norm.lower()
                    if comuna_lower in comunas_bd:
                        comuna_matches[comuna_norm].append('exact')
                    else:
                        # Fuzzy match
                        matches = get_close_matches(comuna_lower, comunas_bd.keys(), n=1, cutoff=0.8)
                        if matches:
                            comuna_matches[comuna_norm].append(f'fuzzy:{matches[0]}')
                        else:
                            comuna_matches[comuna_norm].append('no_match')

            # Analizar países
            if row['pais']:
                paises[row['pais']] += 1

    # =====================================
    # GENERAR REPORTE
    # =====================================

    print("=" * 70)
    print("📋 REPORTE DE ANÁLISIS")
    print("=" * 70)
    print()

    print("📊 TOTALES:")
    print(f"   Total registros en CSV: {total_registros:,}")
    print(f"   Teléfonos únicos en CSV: {len(set(telefonos_csv)):,}")
    print()

    print("🔄 ANÁLISIS DE DUPLICADOS:")
    print(f"   Duplicados dentro del CSV: {len(duplicados_en_csv):,}")
    print(f"   Ya existen en BD actual: {len(ya_existe_en_bd):,}")
    print(f"   ✅ NUEVOS a importar: {len(nuevos_a_importar):,}")
    print()

    if duplicados_en_csv[:5]:
        print("   Ejemplos de duplicados en CSV:")
        for tel, nombre in duplicados_en_csv[:5]:
            print(f"      - {tel}: {nombre}")
        print()

    if ya_existe_en_bd[:5]:
        print("   Ejemplos de clientes que ya existen:")
        for tel, nombre in ya_existe_en_bd[:5]:
            print(f"      - {tel}: {nombre}")
        print()

    print("📧 DATOS OPCIONALES:")
    print(f"   Con email: {emails_count:,} ({emails_count/total_registros*100:.1f}%)")
    print(f"   Con documento: {documentos_count:,} ({documentos_count/total_registros*100:.1f}%)")
    print()

    if documentos_sucios:
        print(f"   ⚠️  Documentos con datos sucios: {len(documentos_sucios)}")
        for doc, nombre in documentos_sucios[:3]:
            print(f"      - {nombre}: '{doc}'")
        print()

    print("📍 ANÁLISIS DE COMUNAS:")
    comunas_con_match = sum(1 for matches in comuna_matches.values() if 'exact' in matches or any('fuzzy' in m for m in matches))
    comunas_sin_match = len(comunas_counter) - comunas_con_match
    total_clientes_con_comuna = sum(comunas_counter.values())

    print(f"   Total clientes con comuna en CSV: {total_clientes_con_comuna:,}")
    print(f"   Comunas únicas en CSV: {len(comunas_counter):,}")
    print(f"   ✅ Comunas normalizables (match en BD): {comunas_con_match:,}")
    print(f"   ⚠️  Comunas sin normalizar: {comunas_sin_match:,}")
    print()

    print("   Top 10 comunas más frecuentes:")
    for comuna, count in comunas_counter.most_common(10):
        match_status = comuna_matches.get(comuna, ['unknown'])[0]
        if match_status == 'exact':
            status_icon = "✅"
        elif 'fuzzy' in match_status:
            status_icon = "🔍"
        else:
            status_icon = "❌"
        print(f"      {status_icon} {comuna}: {count:,} clientes")
    print()

    if paises:
        print("🌍 PAÍSES:")
        for pais, count in paises.most_common(5):
            print(f"   - {pais}: {count:,}")
        print()

    print("=" * 70)
    print("✅ RESUMEN:")
    print("=" * 70)
    print(f"Clientes NUEVOS a importar: {len(nuevos_a_importar):,}")
    print(f"Clientes duplicados (skip): {len(ya_existe_en_bd) + len(duplicados_en_csv):,}")
    print(f"Comunas normalizables: {comunas_con_match}/{len(comunas_counter)} ({comunas_con_match/len(comunas_counter)*100 if comunas_counter else 0:.1f}%)")
    print()
    print("🚀 Listo para proceder a FASE 2 (Importación)")
    print("=" * 70)

    # Guardar detalles para la fase 2
    print()
    print("💾 Guardando mapeo de comunas para FASE 2...")

    mapeo_comunas = {}
    for comuna_csv, matches in comuna_matches.items():
        match = matches[0]
        if match == 'exact':
            # Match exacto
            comuna_bd = comunas_bd[comuna_csv.lower()]
            mapeo_comunas[comuna_csv] = {
                'id': comuna_bd['id'],
                'nombre': comuna_bd['nombre'],
                'tipo': 'exact'
            }
        elif 'fuzzy:' in match:
            # Match fuzzy
            comuna_bd_key = match.split(':')[1]
            comuna_bd = comunas_bd[comuna_bd_key]
            mapeo_comunas[comuna_csv] = {
                'id': comuna_bd['id'],
                'nombre': comuna_bd['nombre'],
                'tipo': 'fuzzy'
            }
        else:
            # Sin match
            mapeo_comunas[comuna_csv] = {
                'id': None,
                'nombre': None,
                'tipo': 'no_match'
            }

    # Guardar mapeo
    import json
    mapeo_file = 'scripts/mapeo_comunas_importacion.json'
    with open(mapeo_file, 'w', encoding='utf-8') as f:
        json.dump(mapeo_comunas, f, indent=2, ensure_ascii=False)

    print(f"✅ Mapeo guardado en: {mapeo_file}")
    print()

    cursor.close()
    conn.close()

if __name__ == '__main__':
    try:
        analizar_csv()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
