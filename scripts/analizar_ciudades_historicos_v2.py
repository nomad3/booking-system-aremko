"""
FASE 1.1: Análisis de ciudades en datos históricos (ServiceHistory)
Versión corregida - obtiene ciudad desde cliente_id

NO MODIFICA DATOS - Solo lectura y análisis
"""
import os
import django
from collections import Counter, defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServiceHistory, Cliente

print("\n" + "="*100)
print("ANÁLISIS DE CIUDADES EN DATOS HISTÓRICOS (crm_service_history → cliente)")
print("="*100 + "\n")

# Total de registros históricos
total_registros = ServiceHistory.objects.count()
print(f"✓ Total de registros históricos: {total_registros:,}\n")

# Obtener todas las ciudades a través de la relación con cliente
print("Obteniendo ciudades de clientes históricos...")
historicos = ServiceHistory.objects.select_related('cliente').all()

ciudades_list = []
sin_cliente = 0
sin_ciudad = 0

for h in historicos:
    if h.cliente:
        if h.cliente.ciudad and h.cliente.ciudad.strip():
            ciudades_list.append(h.cliente.ciudad)
        else:
            sin_ciudad += 1
    else:
        sin_cliente += 1

# Contar ciudades
contador_ciudades = Counter(ciudades_list)

print("="*100)
print("RESUMEN GENERAL")
print("="*100)
print(f"Registros históricos:            {total_registros:>6,}")
print(f"Ciudades únicas:                 {len(contador_ciudades):>6,}")
print(f"Registros con ciudad:            {len(ciudades_list):>6,}")
print(f"Registros sin ciudad:            {sin_ciudad:>6,}")
print(f"Registros sin cliente:           {sin_cliente:>6,}")
print()

# Ordenar por cantidad
ciudades_ordenadas = sorted(contador_ciudades.items(), key=lambda x: x[1], reverse=True)

print("="*100)
print("TOP 50 CIUDADES MÁS FRECUENTES")
print("="*100)
print(f"{'#':<4} {'CIUDAD':<50} {'REGISTROS':>12} {'%':>8}")
print("-"*100)

for i, (ciudad, count) in enumerate(ciudades_ordenadas[:50], 1):
    porcentaje = (count / total_registros) * 100
    print(f"{i:<4} {ciudad:<50} {count:>12,} {porcentaje:>7.2f}%")

# Agrupar variantes similares
print("\n" + "="*100)
print("DETECCIÓN DE VARIANTES (posibles duplicados)")
print("="*100)

grupos = defaultdict(list)
for ciudad, count in contador_ciudades.items():
    # Normalización simple
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
    print("\n✓ No se detectaron variantes obvias")

# Análisis de patrones
print("\n" + "="*100)
print("ANÁLISIS DE PATRONES")
print("="*100)

patrones = {
    'Con "Pto." o "Pto"': 0,
    'Con "Puerto"': 0,
    'Todo minúsculas': 0,
    'Todo mayúsculas': 0,
}

for ciudad in contador_ciudades.keys():
    if 'pto.' in ciudad.lower() or 'pto ' in ciudad.lower():
        patrones['Con "Pto." o "Pto"'] += 1
    if 'puerto' in ciudad.lower():
        patrones['Con "Puerto"'] += 1
    if ciudad.islower():
        patrones['Todo minúsculas'] += 1
    if ciudad.isupper():
        patrones['Todo mayúsculas'] += 1

print()
for patron, count in patrones.items():
    if count > 0:
        print(f"  {patron:<35}: {count:>5} ciudades")

print("\n" + "="*100)
print("RECOMENDACIONES")
print("="*100)
print("""
1. Las ciudades en históricos vienen del campo ciudad de Cliente
2. Se detectaron múltiples variantes que necesitan normalización
3. La normalización debe aplicarse en la tabla Cliente (afecta ambos: actuales e históricos)

PRÓXIMO PASO:
- Crear diccionario de normalización unificado
- Normalizar campo ciudad en tabla ventas_cliente
- Esto automáticamente corregirá las ciudades en históricos
""")

print("\n" + "="*100 + "\n")
