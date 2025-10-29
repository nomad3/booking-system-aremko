"""
Script para diagnosticar un cliente específico y ver qué está inflando sus gastos
"""
import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ServiceHistory, VentaReserva, ReservaServicio
from django.db.models import Sum, Count
from datetime import date

# Cliente a diagnosticar (por teléfono o nombre)
IDENTIFICADOR = "+56984415877"  # Puedes cambiar esto

print("\n" + "="*80)
print(f"🔍 DIAGNÓSTICO DETALLADO: {IDENTIFICADOR}")
print("="*80 + "\n")

# Buscar cliente
try:
    if IDENTIFICADOR.startswith('+'):
        cliente = Cliente.objects.get(telefono=IDENTIFICADOR)
    else:
        cliente = Cliente.objects.get(nombre__icontains=IDENTIFICADOR)
except Cliente.DoesNotExist:
    print(f"❌ Cliente '{IDENTIFICADOR}' no encontrado")
    sys.exit(1)
except Cliente.MultipleObjectsReturned:
    print(f"⚠️  Múltiples clientes con '{IDENTIFICADOR}':")
    clientes = Cliente.objects.filter(telefono=IDENTIFICADOR) if IDENTIFICADOR.startswith('+') else Cliente.objects.filter(nombre__icontains=IDENTIFICADOR)
    for c in clientes:
        print(f"   ID {c.id}: {c.nombre} ({c.telefono})")
    sys.exit(1)

print(f"✅ Cliente encontrado:")
print(f"   ID: {cliente.id}")
print(f"   Nombre: {cliente.nombre}")
print(f"   Email: {cliente.email}")
print(f"   Teléfono: {cliente.telefono}")

# ============================================================================
# ANÁLISIS DE SERVICE HISTORY
# ============================================================================
print("\n" + "="*80)
print("📊 ANÁLISIS DE SERVICE HISTORY (HISTÓRICOS)")
print("="*80 + "\n")

historicos = ServiceHistory.objects.filter(cliente=cliente).order_by('service_date')
total_hist = historicos.count()
suma_hist = historicos.aggregate(Sum('price_paid'))['price_paid__sum'] or 0

print(f"Total servicios históricos: {total_hist:,}")
print(f"Suma total históricos: ${suma_hist:,.0f}")

if total_hist > 0:
    print(f"\n📋 TODOS LOS SERVICIOS HISTÓRICOS ({total_hist} registros):\n")

    # Agrupar por fecha para detectar concentraciones
    from collections import defaultdict
    servicios_por_fecha = defaultdict(list)

    for h in historicos:
        servicios_por_fecha[h.service_date].append({
            'id': h.id,
            'reserva_id': h.reserva_id,
            'servicio': h.service_name,
            'precio': h.price_paid,
            'cantidad': h.quantity
        })

    # Mostrar agrupado por fecha
    for fecha in sorted(servicios_por_fecha.keys()):
        servicios = servicios_por_fecha[fecha]
        total_fecha = sum(s['precio'] for s in servicios)

        marca_sospechosa = ""
        if len(servicios) > 10:
            marca_sospechosa = " ⚠️  SOSPECHOSO: >10 servicios en un día"
        elif fecha == date(2021, 1, 1):
            marca_sospechosa = " ⚠️  FECHA PLACEHOLDER"

        print(f"\n📅 {fecha} | {len(servicios)} servicios | ${total_fecha:,.0f}{marca_sospechosa}")

        # Mostrar todos los servicios de esta fecha
        for s in servicios:
            reserva_str = s['reserva_id'][:20] if s['reserva_id'] else 'sin reserva_id'
            print(f"     ID {s['id']:>6} | Reserva: {reserva_str:<20} | {s['servicio'][:40]:<40} | ${s['precio']:>10,.0f} | Qty: {s['cantidad']}")

# Análisis de fechas
print("\n" + "-"*80)
print("📈 ANÁLISIS DE FECHAS")
print("-"*80 + "\n")

fechas_stats = historicos.values('service_date').annotate(
    count=Count('id'),
    total=Sum('price_paid')
).order_by('-count')

print("Fechas con más servicios:")
for i, fecha_stat in enumerate(fechas_stats[:10], 1):
    fecha = fecha_stat['service_date']
    count = fecha_stat['count']
    total = fecha_stat['total']

    marca = ""
    if count > 10:
        marca = " ⚠️  >10 servicios"
    elif fecha == date(2021, 1, 1):
        marca = " ⚠️  PLACEHOLDER"

    print(f"{i:>2}. {fecha} | {count:>3} servicios | ${total:>12,.0f}{marca}")

# Análisis de duplicados
print("\n" + "-"*80)
print("🔍 DETECCIÓN DE DUPLICADOS")
print("-"*80 + "\n")

duplicados = historicos.values(
    'reserva_id', 'service_date', 'service_name', 'price_paid'
).annotate(count=Count('id')).filter(count__gt=1).order_by('-count')

if duplicados:
    print(f"⚠️  Se encontraron {len(duplicados)} grupos duplicados:\n")
    for dup in duplicados:
        print(f"   {dup['service_date']} | {dup['reserva_id'][:20]:<20} | {dup['service_name'][:30]:<30} | ${dup['price_paid']:>10,.0f} | x{dup['count']}")
else:
    print("✅ No se encontraron duplicados")

# ============================================================================
# ANÁLISIS DE VENTA RESERVA (ACTUALES)
# ============================================================================
print("\n" + "="*80)
print("📊 ANÁLISIS DE VENTA RESERVA (ACTUALES)")
print("="*80 + "\n")

reservas = ReservaServicio.objects.filter(
    venta_reserva__cliente=cliente,
    venta_reserva__estado_pago__in=['pagado', 'parcial']
).select_related('servicio', 'venta_reserva')

total_actuales = reservas.count()
suma_actuales = sum(
    float(rs.servicio.precio_base or 0) * (rs.cantidad_personas or 1)
    for rs in reservas
)

print(f"Total servicios actuales: {total_actuales:,}")
print(f"Suma total actuales: ${suma_actuales:,.0f}")

if total_actuales > 0:
    print(f"\n📋 SERVICIOS ACTUALES:\n")
    for rs in reservas:
        fecha = rs.fecha_agendamiento if rs.fecha_agendamiento else rs.venta_reserva.fecha_reserva.date()
        precio = float(rs.servicio.precio_base or 0) * (rs.cantidad_personas or 1)
        print(f"   {fecha} | {rs.servicio.nombre[:40]:<40} | ${precio:>10,.0f} | {rs.cantidad_personas} personas")

# ============================================================================
# RESUMEN FINAL
# ============================================================================
print("\n" + "="*80)
print("📊 RESUMEN FINAL")
print("="*80 + "\n")

print(f"Servicios históricos:  {total_hist:>6,} | ${suma_hist:>15,.0f}")
print(f"Servicios actuales:    {total_actuales:>6,} | ${suma_actuales:>15,.0f}")
print(f"{'─'*80}")
print(f"TOTAL COMBINADO:       {total_hist + total_actuales:>6,} | ${suma_hist + suma_actuales:>15,.0f}")

# Análisis con filtro de 2021-01-01
hist_sin_placeholder = historicos.exclude(service_date=date(2021, 1, 1))
suma_sin_placeholder = hist_sin_placeholder.aggregate(Sum('price_paid'))['price_paid__sum'] or 0

print(f"\n💡 SI SE EXCLUYE 2021-01-01:")
print(f"Servicios históricos:  {hist_sin_placeholder.count():>6,} | ${suma_sin_placeholder:>15,.0f}")
print(f"Servicios actuales:    {total_actuales:>6,} | ${suma_actuales:>15,.0f}")
print(f"{'─'*80}")
print(f"TOTAL (sin 2021-01-01):{hist_sin_placeholder.count() + total_actuales:>6,} | ${suma_sin_placeholder + suma_actuales:>15,.0f}")

diferencia = suma_hist - suma_sin_placeholder
print(f"\nDiferencia por 2021-01-01: ${diferencia:,.0f} ({diferencia/suma_hist*100:.1f}% del total histórico)")

print("\n" + "="*80 + "\n")
