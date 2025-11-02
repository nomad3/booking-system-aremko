#!/usr/bin/env python3
"""
Script de análisis previo LOCAL (sin conexión a BD)
Analiza el CSV de 13,294 clientes
"""
import csv
from collections import Counter, defaultdict

# Archivo CSV a importar
CSV_FILE = "/Users/jorgeaguilera/Downloads/clientes y servicios - 13294 clientes (1).csv"

def normalizar_telefono(telefono):
    """Normaliza teléfono agregando +56 al inicio"""
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
    """Limpia y normaliza el texto de comuna"""
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
        'Resto Chile': None,
    }

    return especiales.get(comuna, comuna)

def main():
    print("=" * 70)
    print("📊 ANÁLISIS LOCAL DEL CSV DE CLIENTES")
    print("=" * 70)
    print()

    print(f"📁 Archivo: {CSV_FILE}")
    print()

    # Analizar CSV
    print("🔍 Analizando archivo...")

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
        telefonos_vistos = {}
        duplicados_en_csv = []

        # Análisis de comunas
        comunas_counter = Counter()

        # Datos sucios
        documentos_sucios = []

        for row in reader:
            total_registros += 1

            # Analizar teléfono
            telefono_orig = row['Telefono']
            telefono_norm = normalizar_telefono(telefono_orig)

            if telefono_norm:
                telefonos_csv.append(telefono_norm)

                # Detectar duplicados en CSV
                if telefono_norm in telefonos_vistos:
                    duplicados_en_csv.append({
                        'telefono': telefono_norm,
                        'nombre1': telefonos_vistos[telefono_norm],
                        'nombre2': row['nombre']
                    })
                else:
                    telefonos_vistos[telefono_norm] = row['nombre']

            # Contar emails
            if row['Email']:
                emails_count += 1

            # Contar documentos
            documento = row['documento_identidad']
            if documento:
                documentos_count += 1
                # Detectar datos sucios (contiene letras que no son dígitos, puntos o guiones)
                if any(c.isalpha() for c in documento):
                    documentos_sucios.append({
                        'documento': documento,
                        'nombre': row['nombre']
                    })

            # Analizar comunas
            comuna_orig = row['comuna']
            if comuna_orig:
                comuna_norm = normalizar_comuna_texto(comuna_orig)
                if comuna_norm:
                    comunas_csv.append(comuna_norm)
                    comunas_counter[comuna_norm] += 1

            # Analizar países
            if row['pais']:
                paises[row['pais']] += 1

    # Generar reporte
    print()
    print("=" * 70)
    print("📋 REPORTE DE ANÁLISIS")
    print("=" * 70)
    print()

    print("📊 TOTALES:")
    print(f"   Total registros en CSV: {total_registros:,}")
    print(f"   Teléfonos únicos en CSV: {len(set(telefonos_csv)):,}")
    print(f"   Duplicados dentro del CSV: {len(duplicados_en_csv):,}")
    print()

    if duplicados_en_csv[:10]:
        print("   🔄 Ejemplos de duplicados en CSV (mismo teléfono, distinto nombre):")
        for dup in duplicados_en_csv[:10]:
            print(f"      - {dup['telefono']}")
            print(f"          · {dup['nombre1']}")
            print(f"          · {dup['nombre2']}")
        if len(duplicados_en_csv) > 10:
            print(f"      ... y {len(duplicados_en_csv) - 10} más")
        print()

    print("📧 DATOS OPCIONALES:")
    print(f"   Con email: {emails_count:,} ({emails_count/total_registros*100:.1f}%)")
    print(f"   Con documento: {documentos_count:,} ({documentos_count/total_registros*100:.1f}%)")
    print()

    if documentos_sucios:
        print(f"   ⚠️  Documentos con datos potencialmente sucios: {len(documentos_sucios)}")
        for item in documentos_sucios[:5]:
            print(f"      - {item['nombre']}: '{item['documento']}'")
        if len(documentos_sucios) > 5:
            print(f"      ... y {len(documentos_sucios) - 5} más")
        print()

    print("📍 ANÁLISIS DE COMUNAS:")
    total_clientes_con_comuna = sum(comunas_counter.values())
    clientes_sin_comuna = total_registros - total_clientes_con_comuna

    print(f"   Total clientes CON comuna en CSV: {total_clientes_con_comuna:,} ({total_clientes_con_comuna/total_registros*100:.1f}%)")
    print(f"   Total clientes SIN comuna en CSV: {clientes_sin_comuna:,} ({clientes_sin_comuna/total_registros*100:.1f}%)")
    print(f"   Comunas únicas en CSV: {len(comunas_counter):,}")
    print()

    print("   Top 20 comunas más frecuentes:")
    for comuna, count in comunas_counter.most_common(20):
        print(f"      - {comuna}: {count:,} clientes ({count/total_registros*100:.1f}%)")
    print()

    if paises:
        print("🌍 PAÍSES:")
        for pais, count in paises.most_common():
            print(f"   - {pais}: {count:,}")
        print()

    print("=" * 70)
    print("📝 TELÉFONOS NORMALIZADOS:")
    print("=" * 70)
    print()
    print("Todos los teléfonos del CSV se normalizarán agregando +56:")
    print(f"   Ejemplo: 912345678 → +56912345678")
    print()
    print("Teléfonos únicos listos para importar:")
    print(f"   {len(set(telefonos_csv)):,} teléfonos")
    print()

    # Exportar lista de teléfonos
    telefonos_unicos = sorted(set(telefonos_csv))
    output_file = 'scripts/telefonos_para_verificar.txt'
    with open(output_file, 'w') as f:
        for tel in telefonos_unicos:
            f.write(f"{tel}\n")

    print(f"💾 Lista de teléfonos guardada en: {output_file}")
    print(f"   Puedes usar este archivo para verificar cuántos ya existen en la BD")
    print()

    print("=" * 70)
    print("✅ RESUMEN PARA FASE 2:")
    print("=" * 70)
    print(f"Total en CSV: {total_registros:,}")
    print(f"Teléfonos únicos: {len(set(telefonos_csv)):,}")
    print(f"Duplicados en CSV a skip: {len(duplicados_en_csv):,}")
    print(f"Máximo a importar: {len(set(telefonos_csv)) - len(duplicados_en_csv):,}")
    print()
    print("⚠️  NOTA: El número real de importación depende de cuántos")
    print("   teléfonos ya existen en la base de datos actual.")
    print()
    print("📋 SIGUIENTE PASO:")
    print("   1. Revisar el archivo: scripts/telefonos_para_verificar.txt")
    print("   2. Verificar cuántos teléfonos ya existen en BD")
    print("   3. Proceder a FASE 2 (script de importación)")
    print("=" * 70)

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
