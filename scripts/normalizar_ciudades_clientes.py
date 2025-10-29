"""
FASE 3: Aplicar normalización de ciudades a la tabla ventas_cliente

Este script actualiza todas las ciudades en la base de datos usando el diccionario
de normalización creado en FASE 2.

IMPORTANTE:
- Incluye modo DRY-RUN por defecto (no modifica datos)
- Requiere confirmación explícita para aplicar cambios
- Crea log detallado de todos los cambios
- Como ServiceHistory usa cliente.ciudad, esto corrige automáticamente históricos

USO:
    # Ver qué cambios se harían (DRY-RUN):
    python manage.py shell < scripts/normalizar_ciudades_clientes.py

    # Aplicar cambios reales:
    Editar DRY_RUN = False en el código
"""
import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from django.db import transaction
from ventas.models import Cliente
from ventas.data.normalizacion_ciudades import normalizar_ciudad

# ============================================
# CONFIGURACIÓN
# ============================================
DRY_RUN = True  # Cambiar a False para aplicar cambios reales

print("\n" + "="*100)
print("FASE 3: NORMALIZACIÓN DE CIUDADES EN BASE DE DATOS")
print("="*100)
print(f"\nMODO: {'🔍 DRY-RUN (simulación)' if DRY_RUN else '⚠️  APLICAR CAMBIOS REALES'}")
print("="*100 + "\n")

# ============================================
# 1. ANÁLISIS PREVIO
# ============================================
print("📊 ANÁLISIS PREVIO:")
print("-" * 100)

total_clientes = Cliente.objects.count()
clientes_con_ciudad = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').count()
clientes_sin_ciudad = total_clientes - clientes_con_ciudad

print(f"Total de clientes:           {total_clientes:>8,}")
print(f"Clientes con ciudad:         {clientes_con_ciudad:>8,}")
print(f"Clientes sin ciudad:         {clientes_sin_ciudad:>8,}")
print()

# ============================================
# 2. OBTENER CLIENTES A NORMALIZAR
# ============================================
print("🔍 ANALIZANDO CLIENTES QUE NECESITAN NORMALIZACIÓN...")
print("-" * 100)

clientes = Cliente.objects.exclude(ciudad__isnull=True).exclude(ciudad='').all()

cambios = []
sin_cambios = 0

for cliente in clientes:
    ciudad_original = cliente.ciudad
    ciudad_normalizada = normalizar_ciudad(ciudad_original)

    if ciudad_original != ciudad_normalizada:
        cambios.append({
            'id': cliente.id,
            'nombre': cliente.nombre,
            'telefono': cliente.telefono,
            'ciudad_original': ciudad_original,
            'ciudad_normalizada': ciudad_normalizada
        })
    else:
        sin_cambios += 1

print(f"✓ Análisis completado:")
print(f"  • Clientes que NECESITAN cambio:  {len(cambios):>6,}")
print(f"  • Clientes SIN cambio necesario:  {sin_cambios:>6,}")
print()

# ============================================
# 3. MOSTRAR PREVIEW DE CAMBIOS
# ============================================
if cambios:
    print("="*100)
    print("PREVIEW DE CAMBIOS A APLICAR")
    print("="*100)
    print(f"{'#':<5} {'ID':<8} {'CLIENTE':<30} {'CIUDAD ORIGINAL':<25} → {'CIUDAD NORMALIZADA':<25}")
    print("-"*100)

    # Mostrar primeros 50 cambios
    for i, cambio in enumerate(cambios[:50], 1):
        print(f"{i:<5} {cambio['id']:<8} {cambio['nombre'][:28]:<30} {cambio['ciudad_original'][:23]:<25} → {cambio['ciudad_normalizada'][:23]:<25}")

    if len(cambios) > 50:
        print(f"\n... y {len(cambios) - 50:,} cambios más")

    print()

    # ============================================
    # 4. RESUMEN POR CIUDAD
    # ============================================
    print("="*100)
    print("RESUMEN DE NORMALIZACIONES POR CIUDAD")
    print("="*100)

    # Agrupar cambios por ciudad normalizada
    from collections import defaultdict
    cambios_por_ciudad = defaultdict(lambda: {'variantes': defaultdict(int), 'total': 0})

    for cambio in cambios:
        ciudad_norm = cambio['ciudad_normalizada']
        ciudad_orig = cambio['ciudad_original']
        cambios_por_ciudad[ciudad_norm]['variantes'][ciudad_orig] += 1
        cambios_por_ciudad[ciudad_norm]['total'] += 1

    # Ordenar por total de cambios
    ciudades_ordenadas = sorted(cambios_por_ciudad.items(), key=lambda x: x[1]['total'], reverse=True)

    for ciudad_norm, data in ciudades_ordenadas[:20]:
        print(f"\n📍 {ciudad_norm} (Total: {data['total']:,} clientes)")
        for variante, count in sorted(data['variantes'].items(), key=lambda x: x[1], reverse=True):
            if variante != ciudad_norm:  # Solo mostrar si es diferente
                print(f"   • '{variante}' → {count:,} clientes")

    if len(ciudades_ordenadas) > 20:
        print(f"\n... y {len(ciudades_ordenadas) - 20} ciudades más")

    print()

    # ============================================
    # 5. APLICAR CAMBIOS (solo si no es DRY-RUN)
    # ============================================
    if not DRY_RUN:
        print("="*100)
        print("⚠️  APLICANDO CAMBIOS A LA BASE DE DATOS")
        print("="*100)

        confirmacion = input("\n¿Estás seguro de que quieres aplicar estos cambios? (escribe 'SI' para confirmar): ")

        if confirmacion == 'SI':
            print("\n🔄 Aplicando cambios...")

            actualizados = 0
            errores = []

            try:
                with transaction.atomic():
                    for cambio in cambios:
                        try:
                            cliente = Cliente.objects.get(id=cambio['id'])
                            cliente.ciudad = cambio['ciudad_normalizada']
                            cliente.save(update_fields=['ciudad'])
                            actualizados += 1

                            if actualizados % 100 == 0:
                                print(f"  ✓ {actualizados:,} clientes actualizados...")

                        except Exception as e:
                            errores.append({
                                'cliente_id': cambio['id'],
                                'error': str(e)
                            })

                    if errores:
                        print(f"\n⚠️  Se encontraron {len(errores)} errores. Revertiendo cambios...")
                        raise Exception("Errores durante la actualización")

                print(f"\n✅ CAMBIOS APLICADOS EXITOSAMENTE")
                print(f"   • {actualizados:,} clientes actualizados")

            except Exception as e:
                print(f"\n❌ ERROR: {e}")
                print("   • Todos los cambios fueron revertidos (transacción atómica)")
                if errores:
                    print("\nErrores encontrados:")
                    for error in errores[:10]:
                        print(f"   • Cliente {error['cliente_id']}: {error['error']}")
        else:
            print("\n❌ Operación cancelada por el usuario")
    else:
        print("="*100)
        print("🔍 MODO DRY-RUN ACTIVO")
        print("="*100)
        print("""
PARA APLICAR ESTOS CAMBIOS:
1. Edita este script y cambia: DRY_RUN = False
2. Vuelve a ejecutar el script
3. Confirma cuando se te pida
        """)
else:
    print("="*100)
    print("✅ NO HAY CAMBIOS NECESARIOS")
    print("="*100)
    print("Todas las ciudades ya están normalizadas correctamente.")

print()

# ============================================
# 6. CREAR LOG
# ============================================
if cambios and not DRY_RUN:
    log_filename = f"normalizacion_ciudades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    with open(log_filename, 'w', encoding='utf-8') as f:
        f.write("NORMALIZACIÓN DE CIUDADES - LOG\n")
        f.write("="*100 + "\n")
        f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total de cambios: {len(cambios):,}\n")
        f.write("\n" + "="*100 + "\n")
        f.write("DETALLE DE CAMBIOS\n")
        f.write("="*100 + "\n\n")

        for cambio in cambios:
            f.write(f"ID: {cambio['id']}\n")
            f.write(f"Cliente: {cambio['nombre']}\n")
            f.write(f"Teléfono: {cambio['telefono']}\n")
            f.write(f"Cambio: '{cambio['ciudad_original']}' → '{cambio['ciudad_normalizada']}'\n")
            f.write("-"*100 + "\n")

    print(f"📄 Log guardado en: {log_filename}")

print("\n" + "="*100)
print("FASE 3 COMPLETADA")
print("="*100 + "\n")
