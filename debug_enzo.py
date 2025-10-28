"""
Script de debug para investigar inconsistencia en datos de Enzo Magnani
Profile 360°: $275,000 total
Segmentación: $760,000 total ($410,000 actual + $350,000 histórico)
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'aremko_project.settings')
django.setup()

from ventas.models import Cliente, ReservaServicio, ServiceHistory, VentaReserva
from ventas.services.crm_service import CRMService
from decimal import Decimal

# Buscar Enzo por teléfono
ENZO_PHONE = '+56952128260'

print("\n" + "="*80)
print("🔍 DEBUG: Datos de Enzo Magnani Plaza")
print("="*80 + "\n")

try:
    cliente = Cliente.objects.get(telefono=ENZO_PHONE)
    print(f"✅ Cliente encontrado:")
    print(f"   ID: {cliente.id}")
    print(f"   Nombre: {cliente.nombre}")
    print(f"   Teléfono: {cliente.telefono}")
    print(f"   Email: {cliente.email}")
    print()

    # ============= DATOS ACTUALES =============
    print("-" * 80)
    print("📊 SERVICIOS ACTUALES (ReservaServicio)")
    print("-" * 80)

    reservas_servicio = ReservaServicio.objects.filter(
        venta_reserva__cliente=cliente,
        venta_reserva__estado_pago__in=['pagado', 'parcial']
    ).select_related('servicio', 'venta_reserva')

    total_actual = 0
    count_actual = 0

    for rs in reservas_servicio:
        precio_base = float(rs.servicio.precio_base) if rs.servicio.precio_base else 0
        cantidad = rs.cantidad_personas or 1
        precio_total = precio_base * cantidad

        print(f"\n{count_actual + 1}. {rs.servicio.nombre}")
        print(f"   Fecha agendamiento: {rs.fecha_agendamiento}")
        print(f"   Precio base: ${precio_base:,.0f}")
        print(f"   Cantidad personas: {cantidad}")
        print(f"   PRECIO TOTAL: ${precio_total:,.0f}")
        print(f"   VentaReserva ID: {rs.venta_reserva.id}")
        print(f"   VentaReserva.total: ${float(rs.venta_reserva.total):,.0f}")
        print(f"   Estado pago: {rs.venta_reserva.estado_pago}")

        total_actual += precio_total
        count_actual += 1

    print(f"\n{'='*80}")
    print(f"SUBTOTAL ACTUALES: {count_actual} servicios = ${total_actual:,.0f}")
    print(f"{'='*80}\n")

    # ============= DATOS HISTÓRICOS =============
    print("-" * 80)
    print("📊 SERVICIOS HISTÓRICOS (ServiceHistory)")
    print("-" * 80)

    try:
        historicos = ServiceHistory.objects.filter(cliente=cliente)
        total_historico = 0
        count_historico = 0

        for h in historicos:
            precio = float(h.price_paid)
            print(f"\n{count_historico + 1}. {h.service_name}")
            print(f"   Fecha: {h.service_date}")
            print(f"   Tipo: {h.service_type}")
            print(f"   PRECIO: ${precio:,.0f}")
            print(f"   Cantidad: {h.quantity}")

            total_historico += precio
            count_historico += 1

        print(f"\n{'='*80}")
        print(f"SUBTOTAL HISTÓRICOS: {count_historico} servicios = ${total_historico:,.0f}")
        print(f"{'='*80}\n")
    except Exception as e:
        print(f"⚠️  No se pudieron cargar datos históricos: {e}")
        total_historico = 0
        count_historico = 0

    # ============= TOTALES =============
    print("\n" + "="*80)
    print("📈 TOTALES CALCULADOS MANUALMENTE")
    print("="*80)
    print(f"Actuales: {count_actual} servicios = ${total_actual:,.0f}")
    print(f"Históricos: {count_historico} servicios = ${total_historico:,.0f}")
    print(f"TOTAL COMBINADO: {count_actual + count_historico} servicios = ${total_actual + total_historico:,.0f}")
    print("="*80 + "\n")

    # ============= DATOS DE CRM SERVICE =============
    print("-" * 80)
    print("📊 DATOS DE CRMService.get_customer_360()")
    print("-" * 80)

    datos_360 = CRMService.get_customer_360(cliente.id)
    print(f"Total servicios: {datos_360['metricas']['total_servicios']}")
    print(f"  - Actuales: {datos_360['metricas']['servicios_actuales']}")
    print(f"  - Históricos: {datos_360['metricas']['servicios_historicos']}")
    print(f"Gasto total: ${datos_360['metricas']['gasto_total']:,.0f}")
    print(f"Ticket promedio: ${datos_360['metricas']['ticket_promedio']:,.0f}")
    print()

    print("Categorías favoritas:")
    for cat in datos_360['categorias_favoritas']:
        print(f"  - {cat['service_type']}: {cat['cantidad']} servicios, ${cat['gasto']:,.0f}")
    print()

    # ============= COMPARACIÓN =============
    print("\n" + "="*80)
    print("⚠️  COMPARACIÓN DE INCONSISTENCIAS")
    print("="*80)
    print(f"Profile 360° (según screenshot): $275,000")
    print(f"CRMService.get_customer_360(): ${datos_360['metricas']['gasto_total']:,.0f}")
    print(f"Cálculo manual: ${total_actual + total_historico:,.0f}")
    print()
    print(f"Segmentación (según screenshot):")
    print(f"  - Gasto actual: $410,000")
    print(f"  - Gasto histórico: $350,000")
    print(f"  - Total: $760,000")
    print()
    print(f"Cálculo manual:")
    print(f"  - Gasto actual: ${total_actual:,.0f}")
    print(f"  - Gasto histórico: ${total_historico:,.0f}")
    print(f"  - Total: ${total_actual + total_historico:,.0f}")
    print("="*80 + "\n")

    # ============= VERIFICAR SQL QUERY =============
    print("-" * 80)
    print("📊 VERIFICAR SQL QUERY (_get_combined_metrics_for_segmentation)")
    print("-" * 80)

    from django.db import connection

    query = """
    SELECT
        c.id as cliente_id,
        c.nombre,
        -- Servicios actuales
        COUNT(DISTINCT rs.id) as servicios_actuales,
        COALESCE(SUM(
            CAST(s.precio_base AS DECIMAL) * COALESCE(rs.cantidad_personas, 1)
        ), 0) as gasto_actual,
        -- Servicios históricos
        COUNT(DISTINCT sh.id) as servicios_historicos,
        COALESCE(SUM(sh.price_paid), 0) as gasto_historico,
        -- Totales
        (COUNT(DISTINCT rs.id) + COUNT(DISTINCT sh.id)) as total_servicios,
        (COALESCE(SUM(
            CAST(s.precio_base AS DECIMAL) * COALESCE(rs.cantidad_personas, 1)
        ), 0) + COALESCE(SUM(sh.price_paid), 0)) as total_gasto
    FROM ventas_cliente c
    LEFT JOIN ventas_ventareserva vr ON c.id = vr.cliente_id AND vr.estado_pago IN ('pagado', 'parcial')
    LEFT JOIN ventas_reservaservicio rs ON vr.id = rs.venta_reserva_id
    LEFT JOIN ventas_servicio s ON rs.servicio_id = s.id
    LEFT JOIN crm_service_history sh ON c.id = sh.cliente_id
    WHERE c.id = %s
    GROUP BY c.id, c.nombre
    """

    with connection.cursor() as cursor:
        cursor.execute(query, [cliente.id])
        row = cursor.fetchone()
        columns = [col[0] for col in cursor.description]
        result = dict(zip(columns, row))

        print(f"SQL Query result:")
        print(f"  - Servicios actuales: {result['servicios_actuales']}")
        print(f"  - Gasto actual: ${float(result['gasto_actual']):,.0f}")
        print(f"  - Servicios históricos: {result['servicios_historicos']}")
        print(f"  - Gasto histórico: ${float(result['gasto_historico']):,.0f}")
        print(f"  - Total servicios: {result['total_servicios']}")
        print(f"  - Total gasto: ${float(result['total_gasto']):,.0f}")

    print("="*80 + "\n")

except Cliente.DoesNotExist:
    print(f"❌ No se encontró cliente con teléfono {ENZO_PHONE}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
