"""
FASE 1.1: Análisis de ciudades en datos históricos (ServiceHistory)

Este script analiza todas las variantes de ciudades en la tabla crm_service_history
para identificar inconsistencias y patrones de error.

NO MODIFICA DATOS - Solo lectura y análisis
"""
import os
import django
from collections import Counter, defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServiceHistory

print("\n" + "="*100)
print("ANÁLISIS DE CIUDADES EN DATOS HISTÓRICOS (crm_service_history)")
print("="*100 + "\n")

# Verificar que la tabla existe
try:
    total_registros = ServiceHistory.objects.count()
    print(f"✓ Total de registros históricos: {total_registros:,}\n")
except Exception as e:
    print(f"❌ Error: La tabla crm_service_history no existe o no es accesible: {e}")
    exit(1)

# Obtener todas las ciudades
ciudades = ServiceHistory.objects.values_list('city', flat=True)
contador_ciudades = Counter(ciudades)

# Filtrar valores vacíos
ciudades_con_valor = {ciudad: count for ciudad, count in contador_ciudades.items()
                      if ciudad and ciudad.strip()}
ciudades_vacias = contador_ciudades.get('', 0) + contador_ciudades.get(None, 0)

print("="*100)
print("RESUMEN GENERAL")
print("="*100)
print(f"Ciudades únicas (con valor):     {len(ciudades_con_valor):>6,}")
print(f"Registros sin ciudad:            {ciudades_vacias:>6,}")
print(f"Total de registros:              {total_registros:>6,}")
print()

# Ordenar por cantidad (más frecuentes primero)
ciudades_ordenadas = sorted(ciudades_con_valor.items(), key=lambda x: x[1], reverse=True)

print("="*100)
print("TOP 50 CIUDADES MÁS FRECUENTES")
print("="*100)
print(f"{'#':<4} {'CIUDAD':<50} {'REGISTROS':>12} {'%':>8}")
print("-"*100)

for i, (ciudad, count) in enumerate(ciudades_ordenadas[:50], 1):
    porcentaje = (count / total_registros) * 100
    print(f"{i:<4} {ciudad:<50} {count:>12,} {porcentaje:>7.2f}%")

# Agrupar variantes similares (normalización básica para análisis)
print("\n" + "="*100)
print("DETECCIÓN DE VARIANTES (posibles duplicados)")
print("="*100)

# Crear grupos por ciudad normalizada
grupos = defaultdict(list)
for ciudad, count in ciudades_con_valor.items():
    # Normalización simple: lowercase, sin puntos, sin tildes básicas
    ciudad_norm = ciudad.lower().strip()
    ciudad_norm = ciudad_norm.replace('.', '').replace(',', '')
    ciudad_norm = ciudad_norm.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    ciudad_norm = ciudad_norm.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')

    grupos[ciudad_norm].append((ciudad, count))

# Mostrar grupos con múltiples variantes
variantes_detectadas = {norm: variantes for norm, variantes in grupos.items() if len(variantes) > 1}

if variantes_detectadas:
    print("\nSe detectaron variantes para las siguientes ciudades:\n")

    for norm_ciudad, variantes in sorted(variantes_detectadas.items(),
                                         key=lambda x: sum(v[1] for v in x[1]),
                                         reverse=True)[:20]:
        total_grupo = sum(count for _, count in variantes)
        print(f"\n📍 Grupo: '{norm_ciudad}' - Total: {total_grupo:,} registros")
        print("   Variantes:")
        for ciudad_original, count in sorted(variantes, key=lambda x: x[1], reverse=True):
            print(f"      • '{ciudad_original}': {count:,} registros")
else:
    print("\n✓ No se detectaron variantes obvias (todas las ciudades son únicas)")

# Análisis de patrones comunes
print("\n" + "="*100)
print("ANÁLISIS DE PATRONES")
print("="*100)

patrones = {
    'Con "Pto." o "Pto"': 0,
    'Con "Puerto"': 0,
    'Todo minúsculas': 0,
    'Todo mayúsculas': 0,
    'Primera letra mayúscula': 0,
    'Con números': 0,
    'Con caracteres especiales': 0,
}

for ciudad in ciudades_con_valor.keys():
    if 'pto.' in ciudad.lower() or 'pto ' in ciudad.lower():
        patrones['Con "Pto." o "Pto"'] += 1
    if 'puerto' in ciudad.lower():
        patrones['Con "Puerto"'] += 1
    if ciudad.islower():
        patrones['Todo minúsculas'] += 1
    if ciudad.isupper():
        patrones['Todo mayúsculas'] += 1
    if ciudad[0].isupper() and ciudad[1:].islower() if len(ciudad) > 1 else False:
        patrones['Primera letra mayúscula'] += 1
    if any(char.isdigit() for char in ciudad):
        patrones['Con números'] += 1
    if any(char in ciudad for char in ['@', '#', '$', '%', '&', '*', '(', ')', '[', ']']):
        patrones['Con caracteres especiales'] += 1

print()
for patron, count in patrones.items():
    if count > 0:
        print(f"  {patron:<35}: {count:>5} ciudades")

print("\n" + "="*100)
print("RECOMENDACIONES")
print("="*100)
print("""
1. Se detectaron múltiples variantes de las mismas ciudades
2. Es necesario crear un diccionario de normalización
3. Priorizar las ciudades con más registros para el mapeo
4. Considerar casos especiales (abreviaciones, tildes, mayúsculas)

PRÓXIMO PASO:
- Crear diccionario de normalización en FASE 2
- Mapear todas las variantes detectadas a nombres oficiales
""")

print("\n" + "="*100 + "\n")
