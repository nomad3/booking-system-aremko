"""
Script de diagnóstico para investigar gastos inflados en el sistema de tramos
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ServiceHistory, VentaReserva, ReservaServicio
from django.db.models import Sum, Count
from ventas.services.crm_service import CRMService


def diagnosticar_cliente(cliente_nombre):
    """Diagnostica un cliente específico"""
    try:
        cliente = Cliente.objects.get(nombre__icontains=cliente_nombre)

        print("\n" + "="*80)
        print(f"📋 DIAGNÓSTICO: {cliente.nombre} (ID: {cliente.id})")
        print("="*80 + "\n")

        # Servicios históricos
        hist = ServiceHistory.objects.filter(cliente=cliente).order_by('service_date')
        hist_count = hist.count()
        hist_sum = hist.aggregate(Sum('price_paid'))['price_paid__sum'] or 0

        print(f"📊 SERVICIOS HISTÓRICOS (ServiceHistory):")
        print(f"   Total registros: {hist_count}")
        print(f"   Suma total: ${hist_sum:,.0f}")

        if hist_count > 0:
            print(f"\n   Primeros 10 registros:")
            for h in hist[:10]:
                print(f"      {h.service_date} | {h.service_name[:30]:<30} | ${h.price_paid:>10,.0f} | Qty: {h.quantity}")

        # Servicios actuales
        reservas = ReservaServicio.objects.filter(
            venta_reserva__cliente=cliente,
            venta_reserva__estado_pago__in=['pagado', 'parcial']
        ).select_related('servicio', 'venta_reserva')

        actuales_count = reservas.count()
        actuales_sum = sum(
            float(rs.servicio.precio_base or 0) * (rs.cantidad_personas or 1)
            for rs in reservas
        )

        print(f"\n📊 SERVICIOS ACTUALES (VentaReserva):")
        print(f"   Total registros: {actuales_count}")
        print(f"   Suma total: ${actuales_sum:,.0f}")

        if actuales_count > 0:
            print(f"\n   Primeros 10 registros:")
            for rs in reservas[:10]:
                fecha = rs.fecha_agendamiento or rs.venta_reserva.fecha_reserva.date()
                precio = float(rs.servicio.precio_base or 0) * (rs.cantidad_personas or 1)
                print(f"      {fecha} | {rs.servicio.nombre[:30]:<30} | ${precio:>10,.0f} | Qty: {rs.cantidad_personas}")

        # Cálculo usando CRMService
        try:
            datos_360 = CRMService.get_customer_360(cliente.id)
            gasto_crm = datos_360['metricas']['gasto_total']
            print(f"\n💰 GASTO TOTAL (CRMService): ${gasto_crm:,.0f}")
        except Exception as e:
            print(f"\n❌ Error calculando con CRMService: {e}")

        # Detectar posibles duplicados por fecha
        print(f"\n🔍 ANÁLISIS DE DUPLICADOS:")
        fechas_hist = set(hist.values_list('service_date', flat=True))
        fechas_actuales = set()
        for rs in reservas:
            fecha = rs.fecha_agendamiento or rs.venta_reserva.fecha_reserva.date()
            fechas_actuales.add(fecha)

        fechas_comunes = fechas_hist.intersection(fechas_actuales)
        if fechas_comunes:
            print(f"   ⚠️  Fechas que aparecen en AMBOS sistemas: {len(fechas_comunes)}")
            for fecha in sorted(fechas_comunes)[:10]:
                hist_en_fecha = hist.filter(service_date=fecha)
                print(f"      {fecha}: {hist_en_fecha.count()} históricos")
        else:
            print(f"   ✅ No hay fechas duplicadas entre sistemas")

        print("\n" + "="*80 + "\n")

    except Cliente.DoesNotExist:
        print(f"❌ Cliente '{cliente_nombre}' no encontrado")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


def top_clientes_por_gasto(limit=20):
    """Muestra los top N clientes con mayor gasto según ServiceHistory"""
    print("\n" + "="*80)
    print(f"🏆 TOP {limit} CLIENTES CON MAYOR GASTO (ServiceHistory)")
    print("="*80 + "\n")

    clientes_con_gasto = Cliente.objects.annotate(
        gasto_hist=Sum('servicehistory__price_paid'),
        servicios_hist=Count('servicehistory')
    ).filter(gasto_hist__isnull=False).order_by('-gasto_hist')[:limit]

    for i, cliente in enumerate(clientes_con_gasto, 1):
        print(f"{i:>3}. {cliente.nombre[:40]:<40} | ${cliente.gasto_hist:>12,.0f} | {cliente.servicios_hist:>4} servicios")

    print("\n" + "="*80 + "\n")


def estadisticas_generales():
    """Muestra estadísticas generales del sistema"""
    print("\n" + "="*80)
    print("📈 ESTADÍSTICAS GENERALES")
    print("="*80 + "\n")

    total_clientes = Cliente.objects.count()

    # ServiceHistory
    total_hist = ServiceHistory.objects.count()
    clientes_con_hist = ServiceHistory.objects.values('cliente').distinct().count()
    suma_hist = ServiceHistory.objects.aggregate(Sum('price_paid'))['price_paid__sum'] or 0

    print(f"📊 ServiceHistory:")
    print(f"   Total registros: {total_hist:,}")
    print(f"   Clientes únicos: {clientes_con_hist:,}")
    print(f"   Suma total: ${suma_hist:,.0f}")
    if total_hist > 0:
        print(f"   Promedio por registro: ${suma_hist/total_hist:,.0f}")

    # VentaReserva
    total_ventas = VentaReserva.objects.filter(estado_pago__in=['pagado', 'parcial']).count()
    clientes_con_ventas = VentaReserva.objects.filter(
        estado_pago__in=['pagado', 'parcial']
    ).values('cliente').distinct().count()

    print(f"\n📊 VentaReserva (pagadas):")
    print(f"   Total ventas: {total_ventas:,}")
    print(f"   Clientes únicos: {clientes_con_ventas:,}")

    # ReservaServicio
    total_reservas = ReservaServicio.objects.filter(
        venta_reserva__estado_pago__in=['pagado', 'parcial']
    ).count()

    print(f"\n📊 ReservaServicio (pagadas):")
    print(f"   Total reservas: {total_reservas:,}")

    print(f"\n📊 General:")
    print(f"   Total clientes: {total_clientes:,}")
    print(f"   Clientes con historial: {max(clientes_con_hist, clientes_con_ventas):,}")

    print("\n" + "="*80 + "\n")


def detectar_duplicados_masivos():
    """Detecta si hay duplicación masiva de registros"""
    print("\n" + "="*80)
    print("🔍 DETECCIÓN DE DUPLICADOS")
    print("="*80 + "\n")

    # Buscar registros con mismo cliente, fecha y monto
    from django.db.models import Count

    duplicados = ServiceHistory.objects.values(
        'cliente', 'service_date', 'price_paid', 'service_name'
    ).annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')[:20]

    if duplicados:
        print(f"⚠️  Se encontraron {duplicados.count()} grupos de registros duplicados:")
        print(f"\nTop 10 duplicados:")
        for dup in duplicados[:10]:
            cliente = Cliente.objects.get(id=dup['cliente'])
            print(f"   {cliente.nombre[:30]:<30} | {dup['service_date']} | {dup['service_name'][:20]:<20} | ${dup['price_paid']:>10,.0f} | x{dup['count']} veces")
    else:
        print("✅ No se encontraron duplicados exactos")

    print("\n" + "="*80 + "\n")


if __name__ == "__main__":
    print("\n" + "🔬 DIAGNÓSTICO DEL SISTEMA DE GASTOS\n")

    # Estadísticas generales
    estadisticas_generales()

    # Top clientes
    top_clientes_por_gasto(20)

    # Detectar duplicados
    detectar_duplicados_masivos()

    # Diagnosticar casos específicos problemáticos
    print("\n🔍 CASOS ESPECÍFICOS PROBLEMÁTICOS:\n")

    # Clientes con gastos > $5M
    clientes_problematicos = Cliente.objects.annotate(
        gasto_hist=Sum('servicehistory__price_paid')
    ).filter(gasto_hist__gt=5000000).order_by('-gasto_hist')[:5]

    for cliente in clientes_problematicos:
        diagnosticar_cliente(cliente.nombre.split()[0])

    print("\n✅ Diagnóstico completado\n")
