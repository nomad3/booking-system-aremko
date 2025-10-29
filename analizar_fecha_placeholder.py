"""
Script para analizar servicios con fecha 2021-01-01 (sospechosa de ser placeholder)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import ServiceHistory, Cliente
from django.db.models import Count, Sum
from datetime import date

print("\n" + "="*80)
print("🔍 ANÁLISIS DE FECHA PLACEHOLDER: 2021-01-01")
print("="*80 + "\n")

# Servicios en 2021-01-01
fecha_sospechosa = date(2021, 1, 1)
servicios_2021 = ServiceHistory.objects.filter(service_date=fecha_sospechosa)

total_2021 = servicios_2021.count()
suma_2021 = servicios_2021.aggregate(Sum('price_paid'))['price_paid__sum'] or 0
clientes_2021 = servicios_2021.values('cliente').distinct().count()

print(f"📊 ESTADÍSTICAS 2021-01-01:")
print(f"   Total servicios: {total_2021:,}")
print(f"   Suma total: ${suma_2021:,.0f}")
print(f"   Clientes únicos: {clientes_2021:,}")
print(f"   Promedio por servicio: ${suma_2021/total_2021:,.0f}" if total_2021 > 0 else "   N/A")

# Total general
total_general = ServiceHistory.objects.count()
suma_general = ServiceHistory.objects.aggregate(Sum('price_paid'))['price_paid__sum'] or 0

porcentaje_registros = (total_2021 / total_general * 100) if total_general > 0 else 0
porcentaje_monto = (suma_2021 / suma_general * 100) if suma_general > 0 else 0

print(f"\n📈 IMPACTO EN EL TOTAL:")
print(f"   % de registros: {porcentaje_registros:.1f}%")
print(f"   % del monto total: {porcentaje_monto:.1f}%")

# Top clientes con más servicios ese día
print("\n" + "="*80)
print("👥 TOP 20 CLIENTES CON MÁS SERVICIOS EL 2021-01-01")
print("="*80 + "\n")

clientes_top = ServiceHistory.objects.filter(
    service_date=fecha_sospechosa
).values('cliente').annotate(
    count=Count('id'),
    total_gasto=Sum('price_paid')
).order_by('-count')[:20]

for i, item in enumerate(clientes_top, 1):
    try:
        cliente = Cliente.objects.get(id=item['cliente'])
        nombre = cliente.nombre[:40]
    except:
        nombre = "Cliente desconocido"

    print(f"{i:>2}. {nombre:<40} | {item['count']:>3} servicios | ${item['total_gasto']:>12,.0f}")

# Distribución de servicios por cliente
print("\n" + "="*80)
print("📊 DISTRIBUCIÓN DE SERVICIOS POR CLIENTE (2021-01-01)")
print("="*80 + "\n")

from collections import Counter
servicios_por_cliente = ServiceHistory.objects.filter(
    service_date=fecha_sospechosa
).values_list('cliente', flat=True)

distribucion = Counter(servicios_por_cliente)
rangos = {
    '1 servicio': 0,
    '2-5 servicios': 0,
    '6-10 servicios': 0,
    '11-20 servicios': 0,
    '21-50 servicios': 0,
    '50+ servicios': 0
}

for cliente_id, count in distribucion.items():
    if count == 1:
        rangos['1 servicio'] += 1
    elif count <= 5:
        rangos['2-5 servicios'] += 1
    elif count <= 10:
        rangos['6-10 servicios'] += 1
    elif count <= 20:
        rangos['11-20 servicios'] += 1
    elif count <= 50:
        rangos['21-50 servicios'] += 1
    else:
        rangos['50+ servicios'] += 1

for rango, cantidad in rangos.items():
    print(f"   {rango:<20}: {cantidad:>4} clientes")

# Análisis de reserva_id
print("\n" + "="*80)
print("🔑 ANÁLISIS DE RESERVA_ID")
print("="*80 + "\n")

servicios_sin_reserva = servicios_2021.filter(reserva_id='').count()
servicios_con_reserva = total_2021 - servicios_sin_reserva

print(f"   Con reserva_id: {servicios_con_reserva:,} ({servicios_con_reserva/total_2021*100:.1f}%)")
print(f"   Sin reserva_id: {servicios_sin_reserva:,} ({servicios_sin_reserva/total_2021*100:.1f}%)")

# Servicios con precio $0
print("\n" + "="*80)
print("💰 ANÁLISIS DE PRECIOS")
print("="*80 + "\n")

servicios_gratis = servicios_2021.filter(price_paid=0).count()
servicios_pagados = total_2021 - servicios_gratis

print(f"   Con precio > $0: {servicios_pagados:,} ({servicios_pagados/total_2021*100:.1f}%)")
print(f"   Con precio = $0: {servicios_gratis:,} ({servicios_gratis/total_2021*100:.1f}%)")

# Comparación con otras fechas
print("\n" + "="*80)
print("📅 COMPARACIÓN CON OTRAS FECHAS")
print("="*80 + "\n")

fechas_top = ServiceHistory.objects.values('service_date').annotate(
    count=Count('id')
).order_by('-count')[:10]

print("Top 10 fechas con más servicios:")
for i, item in enumerate(fechas_top, 1):
    fecha = item['service_date']
    count = item['count']
    marca = " ⚠️  SOSPECHOSA" if count > 1000 else ""
    print(f"{i:>2}. {fecha} | {count:>5,} servicios{marca}")

print("\n" + "="*80)
print("💡 CONCLUSIONES Y RECOMENDACIONES")
print("="*80 + "\n")

if porcentaje_registros > 20:
    print("⚠️  ALERTA: >20% de los registros están en 2021-01-01")
    print("   Esta fecha probablemente fue usada como placeholder para datos sin fecha.")
    print()
    print("📋 OPCIONES:")
    print("   1. EXCLUIR 2021-01-01 del cálculo de gastos de tramos")
    print("   2. MARCAR estos servicios como 'datos de migración'")
    print("   3. REVISAR el CSV original para recuperar fechas reales")
    print()
    print("🔧 PRÓXIMO PASO:")
    print("   Modificar TramoService para filtrar servicios con fecha 2021-01-01")
elif porcentaje_registros > 10:
    print("⚠️  PRECAUCIÓN: 10-20% de registros en 2021-01-01")
    print("   Considerar revisar si esta fecha es confiable.")
else:
    print("✅ La fecha 2021-01-01 parece normal (<10% de registros)")

print("\n" + "="*80 + "\n")
