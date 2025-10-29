"""
FASE 1.2: Análisis de ciudades en datos actuales (Cliente)

Este script analiza todas las variantes de ciudades en la tabla ventas_cliente
para identificar inconsistencias y patrones de error.

NO MODIFICA DATOS - Solo lectura y análisis
"""
import os
import django
from collections import Counter, defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente

print("\n" + "="*100)
print("ANÁLISIS DE CIUDADES EN DATOS ACTUALES (ventas_cliente)")
print("="*100 + "\n")

# Total de clientes
total_clientes = Cliente.objects.count()
print(f"✓ Total de clientes: {total_clientes:,}\n")

# Obtener todas las ciudades
ciudades = Cliente.objects.values_list('ciudad', flat=True)
contador_ciudades = Counter(ciudades)

# Filtrar valores vacíos
ciudades_con_valor = {ciudad: count for ciudad, count in contador_ciudades.items()
                      if ciudad and ciudad.strip()}
ciudades_vacias = contador_ciudades.get('', 0) + contador_ciudades.get(None, 0)

print("="*100)
print("RESUMEN GENERAL")
print("="*100)
print(f"Ciudades únicas (con valor):     {len(ciudades_con_valor):>6,}")
print(f"Clientes sin ciudad:             {ciudades_vacias:>6,}")
print(f"Total de clientes:               {total_clientes:>6,}")
print()

# Ordenar por cantidad (más frecuentes primero)
ciudades_ordenadas = sorted(ciudades_con_valor.items(), key=lambda x: x[1], reverse=True)

print("="*100)
print("TOP 50 CIUDADES MÁS FRECUENTES")
print("="*100)
print(f"{'#':<4} {'CIUDAD':<50} {'CLIENTES':>12} {'%':>8}")
print("-"*100)

for i, (ciudad, count) in enumerate(ciudades_ordenadas[:50], 1):
    porcentaje = (count / total_clientes) * 100
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
        print(f"\n📍 Grupo: '{norm_ciudad}' - Total: {total_grupo:,} clientes")
        print("   Variantes:")
        for ciudad_original, count in sorted(variantes, key=lambda x: x[1], reverse=True):
            print(f"      • '{ciudad_original}': {count:,} clientes")
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
    'Muy cortos (< 3 caracteres)': 0,
    'Muy largos (> 30 caracteres)': 0,
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
    if ciudad and ciudad[0].isupper() and ciudad[1:].islower() if len(ciudad) > 1 else False:
        patrones['Primera letra mayúscula'] += 1
    if any(char.isdigit() for char in ciudad):
        patrones['Con números'] += 1
    if any(char in ciudad for char in ['@', '#', '$', '%', '&', '*', '(', ')', '[', ']']):
        patrones['Con caracteres especiales'] += 1
    if len(ciudad) < 3:
        patrones['Muy cortos (< 3 caracteres)'] += 1
    if len(ciudad) > 30:
        patrones['Muy largos (> 30 caracteres)'] += 1

print()
for patron, count in patrones.items():
    if count > 0:
        print(f"  {patron:<35}: {count:>5} ciudades")

# Análisis de clientes con servicios vs sin servicios
print("\n" + "="*100)
print("ANÁLISIS DE CLIENTES CON/SIN SERVICIOS")
print("="*100)

from django.db.models import Count, Q, Exists, OuterRef

# Clientes con servicios históricos
clientes_con_historicos = Cliente.objects.filter(
    historial_servicios__isnull=False
).distinct()

# Clientes con servicios actuales
clientes_con_actuales = Cliente.objects.filter(
    reservas__estado_pago__in=['pagado', 'parcial']
).distinct()

# Clientes sin ningún servicio
clientes_sin_servicios = Cliente.objects.exclude(
    Q(historial_servicios__isnull=False) |
    Q(reservas__estado_pago__in=['pagado', 'parcial'])
).distinct()

print(f"\nClientes con servicios históricos:  {clientes_con_historicos.count():>6,}")
print(f"Clientes con servicios actuales:    {clientes_con_actuales.count():>6,}")
print(f"Clientes sin servicios:             {clientes_sin_servicios.count():>6,}")

# Ciudades de clientes sin servicios (potencial limpieza)
if clientes_sin_servicios.exists():
    ciudades_sin_servicios = clientes_sin_servicios.values_list('ciudad', flat=True)
    top_ciudades_sin_servicios = Counter(ciudades_sin_servicios).most_common(10)

    print("\nTop 10 ciudades de clientes SIN servicios:")
    for ciudad, count in top_ciudades_sin_servicios:
        ciudad_display = ciudad if ciudad else "(vacío)"
        print(f"  • {ciudad_display}: {count:,} clientes")

print("\n" + "="*100)
print("COMPARACIÓN CON DATOS HISTÓRICOS")
print("="*100)

# Intentar comparar con datos históricos
try:
    from ventas.models import ServiceHistory

    ciudades_historicas = set(ServiceHistory.objects.exclude(
        city__isnull=True
    ).exclude(
        city=''
    ).values_list('city', flat=True).distinct())

    ciudades_actuales = set(ciudades_con_valor.keys())

    # Ciudades solo en históricos
    solo_historicos = ciudades_historicas - ciudades_actuales
    # Ciudades solo en actuales
    solo_actuales = ciudades_actuales - ciudades_historicas
    # Ciudades en ambos
    en_ambos = ciudades_historicas & ciudades_actuales

    print(f"\nCiudades solo en históricos:        {len(solo_historicos):>6,}")
    print(f"Ciudades solo en actuales:          {len(solo_actuales):>6,}")
    print(f"Ciudades en ambas tablas:           {len(en_ambos):>6,}")

    if solo_historicos and len(solo_historicos) <= 20:
        print("\nCiudades solo en históricos:")
        for ciudad in sorted(solo_historicos):
            print(f"  • {ciudad}")

except Exception as e:
    print(f"\n⚠️  No se pudo comparar con datos históricos: {e}")

print("\n" + "="*100)
print("RECOMENDACIONES")
print("="*100)
print("""
1. Se detectaron múltiples variantes de las mismas ciudades
2. Es necesario crear un diccionario de normalización unificado
3. Considerar eliminar/actualizar clientes sin servicios con datos incorrectos
4. El diccionario debe cubrir AMBAS tablas (históricos y actuales)

PRÓXIMO PASO:
- Crear diccionario de normalización unificado en FASE 2
- Mapear todas las variantes detectadas a nombres oficiales
- Preparar estructura de Región + Comuna de Chile
""")

print("\n" + "="*100 + "\n")
