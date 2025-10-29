"""
FASE 3: Aplicar normalización de ciudades (VERSIÓN PARA EJECUCIÓN)

Este script aplica las normalizaciones a la base de datos.
Es la versión con DRY_RUN = False para aplicar cambios reales.

⚠️  IMPORTANTE: Este script MODIFICA la base de datos
Requiere confirmación escribiendo 'SI' para aplicar los cambios.

USO:
    python manage.py shell < scripts/aplicar_normalizacion_ciudades.py

    Cuando se te pida confirmación, escribe: SI
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
DRY_RUN = False  # ⚠️  APLICAR CAMBIOS REALES

print("\n" + "="*100)
print("FASE 3: NORMALIZACIÓN DE CIUDADES EN BASE DE DATOS")
print("="*100)
print(f"\n⚠️  MODO: APLICAR CAMBIOS REALES A LA BASE DE DATOS")
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

    # Mostrar primeros 20 cambios
    for i, cambio in enumerate(cambios[:20], 1):
        print(f"{i:<5} {cambio['id']:<8} {cambio['nombre'][:28]:<30} {cambio['ciudad_original'][:23]:<25} → {cambio['ciudad_normalizada'][:23]:<25}")

    if len(cambios) > 20:
        print(f"\n... y {len(cambios) - 20:,} cambios más")

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

    for ciudad_norm, data in ciudades_ordenadas[:10]:
        print(f"\n📍 {ciudad_norm} (Total: {data['total']:,} clientes)")
        for variante, count in sorted(data['variantes'].items(), key=lambda x: x[1], reverse=True):
            if variante != ciudad_norm:  # Solo mostrar si es diferente
                print(f"   • '{variante}' → {count:,} clientes")

    if len(ciudades_ordenadas) > 10:
        print(f"\n... y {len(ciudades_ordenadas) - 10} ciudades más")

    print()

    # ============================================
    # 5. CONFIRMACIÓN Y APLICACIÓN
    # ============================================
    print("="*100)
    print("⚠️  CONFIRMACIÓN REQUERIDA")
    print("="*100)
    print(f"""
Se aplicarán {len(cambios):,} cambios a la tabla ventas_cliente.
Esto también afectará automáticamente a los registros históricos (ServiceHistory).

¿Estás seguro de que quieres continuar?
    """)

    confirmacion = input("Escribe 'SI' (en mayúsculas) para confirmar: ")

    if confirmacion == 'SI':
        print("\n" + "="*100)
        print("🔄 APLICANDO CAMBIOS A LA BASE DE DATOS")
        print("="*100)
        print()

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
                            print(f"  ✓ {actualizados:,} / {len(cambios):,} clientes actualizados...")

                    except Exception as e:
                        errores.append({
                            'cliente_id': cambio['id'],
                            'error': str(e)
                        })

                if errores:
                    print(f"\n⚠️  Se encontraron {len(errores)} errores. Revertiendo cambios...")
                    raise Exception("Errores durante la actualización")

            print(f"\n✅ ¡CAMBIOS APLICADOS EXITOSAMENTE!")
            print("="*100)
            print(f"   • {actualizados:,} clientes actualizados")
            print(f"   • {len(set(c['ciudad_normalizada'] for c in cambios))} ciudades normalizadas")
            print()
            print("IMPACTO:")
            print(f"   • Tabla ventas_cliente: {actualizados:,} registros actualizados")
            print(f"   • Tabla crm_service_history: Afectados automáticamente (usa cliente.ciudad)")
            print()
            print("="*100)

            # ============================================
            # 6. CREAR LOG
            # ============================================
            log_filename = f"normalizacion_ciudades_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            with open(log_filename, 'w', encoding='utf-8') as f:
                f.write("NORMALIZACIÓN DE CIUDADES - LOG\n")
                f.write("="*100 + "\n")
                f.write(f"Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total de cambios: {len(cambios):,}\n")
                f.write(f"Cambios aplicados: {actualizados:,}\n")
                f.write("\n" + "="*100 + "\n")
                f.write("DETALLE DE CAMBIOS\n")
                f.write("="*100 + "\n\n")

                for cambio in cambios:
                    f.write(f"ID: {cambio['id']}\n")
                    f.write(f"Cliente: {cambio['nombre']}\n")
                    f.write(f"Teléfono: {cambio['telefono']}\n")
                    f.write(f"Cambio: '{cambio['ciudad_original']}' → '{cambio['ciudad_normalizada']}'\n")
                    f.write("-"*100 + "\n")

            print(f"📄 Log detallado guardado en: {log_filename}")
            print()

        except Exception as e:
            print(f"\n❌ ERROR: {e}")
            print("="*100)
            print("   • Todos los cambios fueron revertidos (transacción atómica)")
            print("   • La base de datos NO fue modificada")
            if errores:
                print("\nErrores encontrados:")
                for error in errores[:10]:
                    print(f"   • Cliente {error['cliente_id']}: {error['error']}")
            print()
    else:
        print("\n❌ OPERACIÓN CANCELADA")
        print("="*100)
        print(f"   • No se escribió: 'SI' (se recibió: '{confirmacion}')")
        print("   • No se aplicaron cambios a la base de datos")
        print()
else:
    print("="*100)
    print("✅ NO HAY CAMBIOS NECESARIOS")
    print("="*100)
    print("Todas las ciudades ya están normalizadas correctamente.")
    print()

print("="*100)
print("FASE 3 COMPLETADA")
print("="*100 + "\n")
