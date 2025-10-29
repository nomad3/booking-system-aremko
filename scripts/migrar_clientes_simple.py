"""
SCRIPT SIMPLIFICADO: Migrar clientes a región + comuna

Versión optimizada sin output excesivo, solo progreso.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Cliente, Region, Comuna
from ventas.data.mapeo_ciudad_region_comuna import obtener_region_comuna

print("\n" + "="*80)
print("MIGRACIÓN SIMPLIFICADA: CIUDAD → REGIÓN + COMUNA")
print("="*80)

# 1. Verificar prerequisitos
regiones_count = Region.objects.count()
comunas_count = Comuna.objects.count()

if regiones_count == 0 or comunas_count == 0:
    print("❌ ERROR: No hay regiones/comunas en la base de datos")
    exit(1)

print(f"\n✓ Regiones: {regiones_count}, Comunas: {comunas_count}")

# 2. Obtener clientes con ciudad
clientes = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').filter(
    region__isnull=True  # Solo los que NO han sido migrados
)

total = clientes.count()
print(f"✓ Clientes a migrar: {total:,}\n")

if total == 0:
    print("✅ Todos los clientes ya están migrados")
    exit(0)

# 3. Preparar migraciones
print("🔄 Analizando...")
migraciones = []
errores = 0

for cliente in clientes:
    ciudad = cliente.ciudad
    codigo_region, nombre_comuna = obtener_region_comuna(ciudad)

    if codigo_region is None:
        # Ciudad extranjera o no mapeada
        continue

    try:
        region = Region.objects.get(codigo=codigo_region)
        comuna = Comuna.objects.get(region=region, nombre=nombre_comuna)

        migraciones.append({
            'cliente_id': cliente.id,
            'region_id': region.id,
            'comuna_id': comuna.id
        })
    except (Region.DoesNotExist, Comuna.DoesNotExist):
        errores += 1
        continue

print(f"✓ {len(migraciones):,} clientes listos para migrar")
print(f"✓ {errores} clientes sin mapeo (skip)\n")

# 4. Aplicar migraciones
print("🔄 Aplicando migraciones...")

try:
    with transaction.atomic():
        actualizados = 0

        for mig in migraciones:
            Cliente.objects.filter(id=mig['cliente_id']).update(
                region_id=mig['region_id'],
                comuna_id=mig['comuna_id']
            )
            actualizados += 1

            if actualizados % 500 == 0:
                print(f"   ✓ {actualizados:,} / {len(migraciones):,}")

        print(f"\n✅ ¡MIGRACIÓN COMPLETADA!")
        print(f"   • Clientes migrados: {actualizados:,}")

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    print("   Todos los cambios fueron revertidos")

# 5. Verificación final
migrados = Cliente.objects.filter(region__isnull=False, comuna__isnull=False).count()
print(f"\n📊 VERIFICACIÓN:")
print(f"   • Total clientes con región+comuna: {migrados:,}")

print("\n" + "="*80 + "\n")
