"""
Script de diagnóstico corregido para investigar gastos inflados
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ServiceHistory
from django.db.models import Sum, Count

print("\n" + "="*80)
print("📈 ESTADÍSTICAS GENERALES")
print("="*80 + "\n")

# ServiceHistory stats
total_hist = ServiceHistory.objects.count()
suma_hist = ServiceHistory.objects.aggregate(Sum('price_paid'))['price_paid__sum'] or 0
promedio = suma_hist / total_hist if total_hist > 0 else 0

print(f"ServiceHistory:")
print(f"  Total registros: {total_hist:,}")
print(f"  Suma total: ${suma_hist:,.0f}")
print(f"  Promedio por registro: ${promedio:,.0f}")

# Top 20 clientes
print("\n" + "="*80)
print("🏆 TOP 20 CLIENTES CON MAYOR GASTO")
print("="*80 + "\n")

# Obtener clientes con más gasto usando related_name correcto
clientes_con_gasto = Cliente.objects.annotate(
    gasto_hist=Sum('historial_servicios__price_paid'),
    servicios_hist=Count('historial_servicios')
).filter(gasto_hist__isnull=False).order_by('-gasto_hist')[:20]

for i, cliente in enumerate(clientes_con_gasto, 1):
    print(f"{i:>2}. {cliente.nombre[:40]:<40} | ${cliente.gasto_hist:>12,.0f} | {cliente.servicios_hist:>4} servicios")

# Detectar duplicados
print("\n" + "="*80)
print("🔍 DETECCIÓN DE DUPLICADOS")
print("="*80 + "\n")

duplicados = ServiceHistory.objects.values(
    'cliente', 'service_date', 'price_paid', 'service_name'
).annotate(
    count=Count('id')
).filter(count__gt=1).order_by('-count')[:20]

if duplicados.exists():
    print(f"⚠️  Se encontraron registros duplicados\n")
    print("Top 10 grupos con más duplicados:")
    for i, dup in enumerate(duplicados[:10], 1):
        try:
            cliente = Cliente.objects.get(id=dup['cliente'])
            nombre = cliente.nombre[:30]
        except:
            nombre = "Cliente desconocido"

        print(f"{i:>2}. {nombre:<30} | {dup['service_date']} | {dup['service_name'][:25]:<25} | ${dup['price_paid']:>10,.0f} | x{dup['count']} veces")
else:
    print("✅ No se encontraron duplicados exactos")

# Análisis de casos específicos problemáticos
print("\n" + "="*80)
print("📋 ANÁLISIS DE CASOS PROBLEMÁTICOS")
print("="*80 + "\n")

# Top 5 clientes con más de $5M
clientes_problematicos = Cliente.objects.annotate(
    gasto_hist=Sum('historial_servicios__price_paid')
).filter(gasto_hist__gt=5000000).order_by('-gasto_hist')[:5]

for cliente in clientes_problematicos:
    print(f"\n{'─'*80}")
    print(f"Cliente: {cliente.nombre} (ID: {cliente.id})")
    print(f"Gasto total: ${cliente.gasto_hist:,.0f}")
    print(f"{'─'*80}")

    # Servicios de este cliente
    servicios = ServiceHistory.objects.filter(cliente=cliente).order_by('service_date')
    total_servicios = servicios.count()

    print(f"Total de servicios: {total_servicios}")

    # Primeros 5 servicios
    print("\nPrimeros 5 servicios:")
    for s in servicios[:5]:
        print(f"  {s.service_date} | {s.service_name[:30]:<30} | ${s.price_paid:>10,.0f} | Qty: {s.quantity}")

    # Últimos 5 servicios
    print("\nÚltimos 5 servicios:")
    for s in servicios.reverse()[:5]:
        print(f"  {s.service_date} | {s.service_name[:30]:<30} | ${s.price_paid:>10,.0f} | Qty: {s.quantity}")

    # Análisis de fechas duplicadas
    fechas_duplicadas = servicios.values('service_date').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')

    if fechas_duplicadas.exists():
        print(f"\n⚠️  Fechas con múltiples servicios: {fechas_duplicadas.count()}")
        print("Top 3 fechas:")
        for fecha_dup in fechas_duplicadas[:3]:
            print(f"  {fecha_dup['service_date']}: {fecha_dup['count']} servicios")
            # Mostrar servicios en esa fecha
            servicios_fecha = servicios.filter(service_date=fecha_dup['service_date'])
            for sf in servicios_fecha[:3]:
                print(f"    - {sf.service_name[:25]:<25} | ${sf.price_paid:>10,.0f}")

# Comparación con VentaReserva
print("\n" + "="*80)
print("🔍 COMPARACIÓN CON VENTARESERVA")
print("="*80 + "\n")

from ventas.models import VentaReserva, ReservaServicio

for cliente in clientes_problematicos[:3]:
    print(f"\nCliente: {cliente.nombre}")

    # Gasto en ServiceHistory
    gasto_hist = ServiceHistory.objects.filter(cliente=cliente).aggregate(
        Sum('price_paid')
    )['price_paid__sum'] or 0

    # Gasto en VentaReserva (actual)
    reservas = ReservaServicio.objects.filter(
        venta_reserva__cliente=cliente,
        venta_reserva__estado_pago__in=['pagado', 'parcial']
    ).select_related('servicio')

    gasto_actual = sum(
        float(rs.servicio.precio_base or 0) * (rs.cantidad_personas or 1)
        for rs in reservas
    )

    print(f"  Gasto histórico (ServiceHistory): ${gasto_hist:,.0f}")
    print(f"  Gasto actual (VentaReserva):      ${gasto_actual:,.0f}")
    print(f"  Total combinado:                   ${float(gasto_hist) + gasto_actual:,.0f}")

print("\n" + "="*80)
print("✅ DIAGNÓSTICO COMPLETADO")
print("="*80 + "\n")
