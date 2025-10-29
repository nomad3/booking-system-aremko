"""
FASE 4: Migración de clientes de ciudad → región + comuna

Este script migra los clientes existentes desde el campo ciudad (texto libre)
a los nuevos campos region y comuna (ForeignKeys).

IMPORTANTE:
- Usa el mapeo de ciudad normalizada → (región, comuna)
- Solo actualiza clientes con ciudad mapeada
- No modifica clientes extranjeros o sin ciudad
- Usa .update() para evitar validaciones del modelo

PREREQUISITOS:
1. Tablas Region y Comuna creadas (python manage.py migrate)
2. Fixtures cargadas (python manage.py loaddata regiones_comunas_chile)

USO:
    python manage.py shell < scripts/migrar_clientes_a_region_comuna.py
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Cliente, Region, Comuna
from ventas.data.mapeo_ciudad_region_comuna import obtener_region_comuna

print("\n" + "="*100)
print("MIGRACIÓN DE CLIENTES: CIUDAD → REGIÓN + COMUNA")
print("="*100 + "\n")

# ============================================
# 1. VERIFICAR PREREQUISITOS
# ============================================
print("📋 VERIFICANDO PREREQUISITOS...")
print("-" * 100)

regiones_count = Region.objects.count()
comunas_count = Comuna.objects.count()

if regiones_count == 0:
    print("❌ ERROR: No hay regiones en la base de datos")
    print("   Ejecuta primero: python manage.py loaddata regiones_comunas_chile")
    exit(1)

if comunas_count == 0:
    print("❌ ERROR: No hay comunas en la base de datos")
    print("   Ejecuta primero: python manage.py loaddata regiones_comunas_chile")
    exit(1)

print(f"✓ Regiones cargadas:  {regiones_count}")
print(f"✓ Comunas cargadas:   {comunas_count}")
print()

# ============================================
# 2. ANÁLISIS PREVIO
# ============================================
print("📊 ANÁLISIS DE CLIENTES:")
print("-" * 100)

total_clientes = Cliente.objects.count()
clientes_con_ciudad = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').count()
clientes_sin_ciudad = total_clientes - clientes_con_ciudad

# Clientes ya migrados (tienen region y comuna)
clientes_ya_migrados = Cliente.objects.filter(
    region__isnull=False,
    comuna__isnull=False
).count()

print(f"Total de clientes:                {total_clientes:>8,}")
print(f"Clientes con ciudad:              {clientes_con_ciudad:>8,}")
print(f"Clientes sin ciudad:              {clientes_sin_ciudad:>8,}")
print(f"Clientes ya con región+comuna:    {clientes_ya_migrados:>8,}")
print()

# ============================================
# 3. ANALIZAR CLIENTES A MIGRAR
# ============================================
print("🔍 ANALIZANDO MAPEO CIUDAD → REGIÓN + COMUNA...")
print("-" * 100)

clientes = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').all()

migraciones = []
sin_mapeo = []
extranjeros = []

for cliente in clientes:
    # Si ya tiene región y comuna, skip
    if cliente.region_id and cliente.comuna_id:
        continue

    ciudad = cliente.ciudad
    codigo_region, nombre_comuna = obtener_region_comuna(ciudad)

    if codigo_region is None and nombre_comuna is None:
        # Ciudad extranjera o no mapeada
        if ciudad in ['Estados Unidos', 'Santa Fe, NM', 'El Cajón, CA', 'Argentina',
                      'Buenos Aires', 'Extranjero']:
            extranjeros.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'ciudad': ciudad
            })
        else:
            sin_mapeo.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'ciudad': ciudad
            })
    else:
        # Buscar región y comuna en la base de datos
        try:
            region = Region.objects.get(codigo=codigo_region)
            comuna = Comuna.objects.get(region=region, nombre=nombre_comuna)

            migraciones.append({
                'cliente_id': cliente.id,
                'nombre': cliente.nombre,
                'ciudad': ciudad,
                'region': region,
                'comuna': comuna
            })
        except Region.DoesNotExist:
            print(f"⚠️  Región '{codigo_region}' no existe para ciudad '{ciudad}'")
            sin_mapeo.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'ciudad': ciudad
            })
        except Comuna.DoesNotExist:
            print(f"⚠️  Comuna '{nombre_comuna}' no existe en región '{codigo_region}'")
            sin_mapeo.append({
                'id': cliente.id,
                'nombre': cliente.nombre,
                'ciudad': ciudad
            })

print(f"✓ Análisis completado:")
print(f"  • Clientes a migrar:              {len(migraciones):>6,}")
print(f"  • Clientes extranjeros (skip):    {len(extranjeros):>6,}")
print(f"  • Clientes sin mapeo (skip):      {len(sin_mapeo):>6,}")
print()

# ============================================
# 4. MOSTRAR PREVIEW
# ============================================
if migraciones:
    print("="*100)
    print("PREVIEW DE MIGRACIONES")
    print("="*100)
    print(f"{'#':<5} {'CLIENTE':<30} {'CIUDAD':<25} → {'REGIÓN + COMUNA':<40}")
    print("-"*100)

    for i, mig in enumerate(migraciones[:20], 1):
        destino = f"{mig['region'].nombre} / {mig['comuna'].nombre}"
        print(f"{i:<5} {mig['nombre'][:28]:<30} {mig['ciudad'][:23]:<25} → {destino[:38]:<40}")

    if len(migraciones) > 20:
        print(f"\n... y {len(migraciones) - 20:,} migraciones más")

    print()

    # Resumen por región
    print("="*100)
    print("RESUMEN DE MIGRACIONES POR REGIÓN")
    print("="*100)

    from collections import defaultdict
    por_region = defaultdict(lambda: {'comunas': defaultdict(int), 'total': 0})

    for mig in migraciones:
        region_nombre = mig['region'].nombre
        comuna_nombre = mig['comuna'].nombre
        por_region[region_nombre]['comunas'][comuna_nombre] += 1
        por_region[region_nombre]['total'] += 1

    for region_nombre in sorted(por_region.keys(), key=lambda x: por_region[x]['total'], reverse=True)[:10]:
        data = por_region[region_nombre]
        print(f"\n📍 {region_nombre} (Total: {data['total']:,} clientes)")
        for comuna_nombre, count in sorted(data['comunas'].items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"   • {comuna_nombre}: {count:,} clientes")

    print()

    # ============================================
    # 5. APLICAR MIGRACIONES
    # ============================================
    print("="*100)
    print("🔄 APLICANDO MIGRACIONES")
    print("="*100)
    print(f"\nSe migrarán {len(migraciones):,} clientes...")
    print()

    actualizados = 0
    errores = []
    inicio = datetime.now()

    try:
        with transaction.atomic():
            for mig in migraciones:
                try:
                    # Usar .update() para evitar validaciones del modelo
                    Cliente.objects.filter(id=mig['cliente_id']).update(
                        region=mig['region'],
                        comuna=mig['comuna']
                    )
                    actualizados += 1

                    if actualizados % 100 == 0:
                        print(f"  ✓ {actualizados:,} / {len(migraciones):,} clientes migrados...")

                except Exception as e:
                    errores.append({
                        'cliente_id': mig['cliente_id'],
                        'error': str(e)
                    })

            if errores:
                print(f"\n⚠️  Se encontraron {len(errores)} errores. Revertiendo cambios...")
                raise Exception("Errores durante la migración")

        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()

        print(f"\n✅ ¡MIGRACIÓN COMPLETADA EXITOSAMENTE!")
        print("="*100)
        print(f"   • Clientes migrados:              {actualizados:,}")
        print(f"   • Regiones únicas:                {len(por_region)}")
        print(f"   • Tiempo de ejecución:            {duracion:.2f} segundos")
        print()
        print("RESUMEN:")
        print(f"   • Clientes con región+comuna:     {actualizados:,}")
        print(f"   • Clientes extranjeros (sin cambio):  {len(extranjeros):,}")
        print(f"   • Clientes sin mapeo (sin cambio):    {len(sin_mapeo):,}")
        print()
        print("="*100)

    except Exception as e:
        fin = datetime.now()
        duracion = (fin - inicio).total_seconds()

        print(f"\n❌ ERROR DURANTE LA MIGRACIÓN")
        print("="*100)
        print(f"   Error: {e}")
        print(f"   Tiempo transcurrido: {duracion:.2f} segundos")
        print(f"   Clientes procesados antes del error: {actualizados:,}")
        print()
        print("IMPORTANTE:")
        print("   • Todos los cambios fueron revertidos (transacción atómica)")
        print("   • La base de datos NO fue modificada")
        print()

        if errores:
            print("Errores encontrados:")
            for error in errores[:10]:
                print(f"   • Cliente {error['cliente_id']}: {error['error']}")
            if len(errores) > 10:
                print(f"   ... y {len(errores) - 10} errores más")
        print()

else:
    print("="*100)
    print("✅ NO HAY CLIENTES PARA MIGRAR")
    print("="*100)
    print("Todos los clientes ya tienen región + comuna asignadas.")
    print()

# ============================================
# 6. MOSTRAR CLIENTES SIN MAPEO
# ============================================
if sin_mapeo:
    print("="*100)
    print("⚠️  CLIENTES SIN MAPEO")
    print("="*100)
    print(f"\n{len(sin_mapeo)} clientes no tienen mapeo definido:\n")

    for i, cliente in enumerate(sin_mapeo[:10], 1):
        print(f"  {i}. Cliente {cliente['id']}: '{cliente['ciudad']}'")

    if len(sin_mapeo) > 10:
        print(f"\n  ... y {len(sin_mapeo) - 10} más")

    print("\nEstos clientes requieren agregar mapeo manual en:")
    print("  ventas/data/mapeo_ciudad_region_comuna.py")
    print()

print("="*100)
print("MIGRACIÓN COMPLETADA")
print("="*100 + "\n")
