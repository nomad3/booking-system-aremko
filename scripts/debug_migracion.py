"""
Script de debug para ver por qué falló la migración
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, Region, Comuna
from ventas.data.mapeo_ciudad_region_comuna import obtener_region_comuna

print("\n" + "="*80)
print("DEBUG: ¿Por qué no se migraron los clientes?")
print("="*80 + "\n")

# 1. Verificar regiones y comunas
print("1. Regiones en BD:", Region.objects.count())
print("2. Comunas en BD:", Comuna.objects.count())

# 2. Ver clientes con ciudad
clientes_con_ciudad = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='')[:5]
print(f"\n3. Clientes con ciudad (primeros 5):")
for c in clientes_con_ciudad:
    print(f"   - ID {c.id}: ciudad='{c.ciudad}'")
    codigo_region, nombre_comuna = obtener_region_comuna(c.ciudad)
    print(f"     Mapeo → region={codigo_region}, comuna={nombre_comuna}")

    if codigo_region:
        try:
            region = Region.objects.get(codigo=codigo_region)
            print(f"     ✓ Región encontrada: {region.nombre}")
            comuna = Comuna.objects.get(region=region, nombre=nombre_comuna)
            print(f"     ✓ Comuna encontrada: {comuna.nombre}")
        except Region.DoesNotExist:
            print(f"     ✗ Región {codigo_region} NO EXISTE en BD")
        except Comuna.DoesNotExist:
            print(f"     ✗ Comuna {nombre_comuna} NO EXISTE en BD para región {codigo_region}")

# 3. Verificar si el módulo de mapeo funciona
print(f"\n4. Probando mapeo directamente:")
test_ciudades = ['Puerto Montt', 'Santiago', 'Puerto Varas']
for ciudad in test_ciudades:
    codigo, comuna = obtener_region_comuna(ciudad)
    print(f"   '{ciudad}' → region={codigo}, comuna={comuna}")

print("\n" + "="*80 + "\n")
