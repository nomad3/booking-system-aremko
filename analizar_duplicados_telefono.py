"""
Script para detectar clientes duplicados por teléfono
Encuentra casos donde el mismo número existe con y sin el signo +
Ejemplo: +56958655810 vs 56958655810
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente
from collections import defaultdict

print("\n" + "="*80)
print("🔍 ANÁLISIS DE DUPLICADOS EN TELÉFONOS DE CLIENTES")
print("="*80 + "\n")

# Obtener todos los clientes
clientes = Cliente.objects.all()
total_clientes = clientes.count()

print(f"Total de clientes en la BD: {total_clientes:,}\n")

# Agrupar clientes por teléfono normalizado
telefonos_normalizados = defaultdict(list)

for cliente in clientes:
    telefono_original = cliente.telefono

    # Normalizar: si no empieza con +, agregarlo
    if telefono_original:
        telefono_normalizado = telefono_original if telefono_original.startswith('+') else f'+{telefono_original}'

        telefonos_normalizados[telefono_normalizado].append({
            'id': cliente.id,
            'nombre': cliente.nombre,
            'telefono_original': telefono_original,
            'email': cliente.email or 'sin email'
        })

# Encontrar duplicados (mismo número normalizado, múltiples clientes)
duplicados = {tel: clientes for tel, clientes in telefonos_normalizados.items() if len(clientes) > 1}

print("="*80)
print("📊 RESULTADOS")
print("="*80 + "\n")

if duplicados:
    print(f"⚠️  SE ENCONTRARON {len(duplicados)} NÚMEROS CON DUPLICADOS\n")
    print(f"Total de registros duplicados: {sum(len(clientes) for clientes in duplicados.values()):,}\n")

    print("="*80)
    print("📋 DETALLE DE DUPLICADOS")
    print("="*80 + "\n")

    for i, (telefono_normalizado, clientes_dup) in enumerate(sorted(duplicados.items()), 1):
        print(f"\n{i}. Número normalizado: {telefono_normalizado}")
        print(f"   Cantidad de registros: {len(clientes_dup)}")
        print(f"   {'-'*70}")

        for cliente in clientes_dup:
            print(f"   ID: {cliente['id']:<6} | Tel Original: {cliente['telefono_original']:<20} | {cliente['nombre'][:30]:<30} | {cliente['email'][:30]}")

    # Análisis de patrones
    print("\n" + "="*80)
    print("📈 ANÁLISIS DE PATRONES")
    print("="*80 + "\n")

    # Casos con + vs sin +
    casos_con_sin_mas = 0
    for telefono_normalizado, clientes_dup in duplicados.items():
        telefonos_originales = set(c['telefono_original'] for c in clientes_dup)
        tiene_con_mas = any(t.startswith('+') for t in telefonos_originales)
        tiene_sin_mas = any(not t.startswith('+') for t in telefonos_originales)

        if tiene_con_mas and tiene_sin_mas:
            casos_con_sin_mas += 1

    print(f"Números con variante '+' y sin '+': {casos_con_sin_mas}")
    print(f"Otros tipos de duplicados: {len(duplicados) - casos_con_sin_mas}")

    # Estadísticas de duplicación
    print("\n" + "="*80)
    print("📊 ESTADÍSTICAS DE DUPLICACIÓN")
    print("="*80 + "\n")

    duplicacion_counts = defaultdict(int)
    for clientes_dup in duplicados.values():
        duplicacion_counts[len(clientes_dup)] += 1

    for count in sorted(duplicacion_counts.keys()):
        print(f"   {count} registros del mismo número: {duplicacion_counts[count]} casos")

    # Sugerencias de limpieza
    print("\n" + "="*80)
    print("💡 RECOMENDACIONES")
    print("="*80 + "\n")

    total_registros_eliminar = sum(len(clientes) - 1 for clientes in duplicados.values())

    print(f"1. Total de registros que se podrían consolidar: {total_registros_eliminar:,}")
    print(f"2. Clientes únicos después de consolidar: {total_clientes - total_registros_eliminar:,}")
    print(f"3. Reducción: {total_registros_eliminar / total_clientes * 100:.2f}%")
    print("\n⚠️  IMPORTANTE:")
    print("   - Revisa manualmente los duplicados antes de eliminar")
    print("   - Verifica cuál registro tiene más datos completos")
    print("   - Considera migrar historial de servicios/reservas al registro a mantener")
    print("   - La nueva validación previene futuros duplicados de este tipo")

else:
    print("✅ No se encontraron duplicados por diferencia de signo +")
    print("   La base de datos está limpia en este aspecto.\n")

# Análisis adicional: teléfonos sin +
print("\n" + "="*80)
print("📱 ANÁLISIS DE FORMATO DE TELÉFONOS")
print("="*80 + "\n")

telefonos_sin_mas = Cliente.objects.exclude(telefono__startswith='+').count()
telefonos_con_mas = Cliente.objects.filter(telefono__startswith='+').count()

print(f"Teléfonos CON signo '+':    {telefonos_con_mas:>6,} ({telefonos_con_mas/total_clientes*100:>5.1f}%)")
print(f"Teléfonos SIN signo '+':    {telefonos_sin_mas:>6,} ({telefonos_sin_mas/total_clientes*100:>5.1f}%)")
print(f"{'─'*80}")
print(f"Total:                      {total_clientes:>6,} (100.0%)")

print("\n💡 Con la nueva validación implementada:")
print("   - Todos los números nuevos se normalizarán con '+'")
print("   - Los números existentes se mantendrán hasta que se editen")
print("   - No se crearán nuevos duplicados del tipo '+56...' vs '56...'")

print("\n" + "="*80 + "\n")
