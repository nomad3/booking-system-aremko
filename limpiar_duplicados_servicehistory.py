"""
Script para limpiar registros duplicados en ServiceHistory
Mantiene solo 1 copia de cada servicio único
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServiceHistory
from django.db.models import Count
from django.db import transaction

print("\n" + "="*80)
print("🧹 LIMPIEZA DE DUPLICADOS EN SERVICEHISTORY")
print("="*80 + "\n")

# PASO 1: Identificar duplicados
print("📊 Paso 1: Identificando duplicados...\n")

duplicados = ServiceHistory.objects.values(
    'cliente', 'reserva_id', 'service_date', 'price_paid', 'service_name', 'quantity'
).annotate(
    count=Count('id'),
    ids=Count('id')  # Para contar
).filter(count__gt=1).order_by('-count')

total_grupos_duplicados = len(duplicados)
print(f"Total de grupos duplicados encontrados: {total_grupos_duplicados:,}\n")

if total_grupos_duplicados == 0:
    print("✅ No se encontraron duplicados. La base de datos está limpia.\n")
    exit(0)

# Mostrar top 10
print("Top 10 grupos con más duplicados:")
for i, dup in enumerate(duplicados[:10], 1):
    from ventas.models import Cliente
    try:
        cliente = Cliente.objects.get(id=dup['cliente'])
        nombre = cliente.nombre[:30]
    except:
        nombre = "Cliente desconocido"

    print(f"{i:>2}. {nombre:<30} | {dup['service_date']} | {dup['service_name'][:25]:<25} | ${dup['price_paid']:>10,.0f} | x{dup['count']} veces")

# PASO 2: Calcular estadísticas
print("\n" + "="*80)
print("📈 ESTADÍSTICAS DE LIMPIEZA")
print("="*80 + "\n")

registros_antes = ServiceHistory.objects.count()
registros_a_eliminar = 0

for dup in duplicados:
    registros_a_eliminar += (dup['count'] - 1)  # Eliminar todos menos 1

print(f"Registros actuales:      {registros_antes:>10,}")
print(f"Registros a eliminar:    {registros_a_eliminar:>10,}")
print(f"Registros después:       {registros_antes - registros_a_eliminar:>10,}")
print(f"Reducción:               {registros_a_eliminar / registros_antes * 100:>10.1f}%")

# PASO 3: Confirmación
print("\n" + "="*80)
print("⚠️  CONFIRMACIÓN REQUERIDA")
print("="*80 + "\n")

respuesta = input(f"¿Deseas eliminar {registros_a_eliminar:,} registros duplicados? (escribe 'SI' para confirmar): ")

if respuesta.strip().upper() != 'SI':
    print("\n❌ Operación cancelada. No se eliminaron registros.\n")
    exit(0)

# PASO 4: Limpieza
print("\n" + "="*80)
print("🔧 EJECUTANDO LIMPIEZA")
print("="*80 + "\n")

eliminados = 0
errores = 0

with transaction.atomic():
    for i, dup in enumerate(duplicados, 1):
        try:
            # Obtener todos los registros de este grupo
            registros = ServiceHistory.objects.filter(
                cliente_id=dup['cliente'],
                reserva_id=dup['reserva_id'],
                service_date=dup['service_date'],
                price_paid=dup['price_paid'],
                service_name=dup['service_name'],
                quantity=dup['quantity']
            ).order_by('id')

            # Conservar el primero, eliminar el resto
            registros_a_borrar = list(registros[1:])
            count = len(registros_a_borrar)

            for registro in registros_a_borrar:
                registro.delete()

            eliminados += count

            # Mostrar progreso cada 100 grupos
            if i % 100 == 0:
                print(f"  Procesados {i:,}/{total_grupos_duplicados:,} grupos ({eliminados:,} registros eliminados)...")

        except Exception as e:
            errores += 1
            print(f"  ❌ Error en grupo {i}: {e}")

# PASO 5: Verificación
print("\n" + "="*80)
print("✅ LIMPIEZA COMPLETADA")
print("="*80 + "\n")

registros_despues = ServiceHistory.objects.count()

print(f"Registros antes:         {registros_antes:>10,}")
print(f"Registros eliminados:    {eliminados:>10,}")
print(f"Registros después:       {registros_despues:>10,}")
print(f"Errores:                 {errores:>10,}")

# Verificar que no quedan duplicados
duplicados_restantes = ServiceHistory.objects.values(
    'cliente', 'reserva_id', 'service_date', 'price_paid', 'service_name', 'quantity'
).annotate(count=Count('id')).filter(count__gt=1).count()

print(f"\nDuplicados restantes:    {duplicados_restantes:>10,}")

if duplicados_restantes == 0:
    print("\n🎉 ¡Base de datos limpia! No quedan duplicados.")
else:
    print(f"\n⚠️  Aún quedan {duplicados_restantes} grupos duplicados. Ejecuta el script nuevamente.")

print("\n" + "="*80)
print("📌 PRÓXIMOS PASOS:")
print("   1. Ejecuta nuevamente: python diagnostico_gastos_fix.py")
print("   2. Verifica que los gastos ahora son correctos")
print("   3. Ejecuta: python manage.py calcular_tramos_clientes --dry-run")
print("="*80 + "\n")
