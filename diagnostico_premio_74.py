#!/usr/bin/env python
"""
Script de diagnóstico para Premio #74
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'booking_system.settings')
django.setup()

from ventas.models import VentaReserva, ReservaServicio, ClientePremio, Cliente
from django.utils import timezone

print("\n" + "=" * 80)
print("🔍 DIAGNÓSTICO PREMIO #74")
print("=" * 80 + "\n")

# Premio #74
try:
    premio = ClientePremio.objects.get(id=74)
    print(f"📦 PREMIO #74:")
    print(f"  Cliente: {premio.cliente.nombre if premio.cliente else 'N/A'}")
    print(f"  Premio: {premio.premio.nombre if premio.premio else 'N/A'}")
    print(f"  Tipo: {premio.premio.tipo if premio.premio else 'N/A'}")
    print(f"  Fecha generación: {premio.fecha_generacion}")
    print(f"  Fecha ganado: {premio.fecha_ganado}")
    print(f"  Estado: {premio.estado}")
    print(f"  Gasto total al ganar: ${premio.gasto_total_al_ganar:,.0f}")
    print(f"  Tramo al ganar: {premio.tramo_al_ganar}")
    print()

    # Buscar reserva 3923
    print("📋 RESERVA #3923:")
    try:
        reserva = VentaReserva.objects.get(id=3923)
        print(f"  Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}")
        print(f"  Fecha reserva: {reserva.fecha_reserva}")
        print(f"  Estado: {reserva.estado_reserva}")
        print(f"  Total: ${reserva.total:,.0f}")
        print()

        # Servicios de la reserva
        print("🔧 SERVICIOS DE LA RESERVA #3923:")
        servicios = reserva.reservaservicios.all().order_by('fecha_agendamiento', 'hora_inicio')
        for i, rs in enumerate(servicios, 1):
            print(f"  {i}. {rs.servicio.nombre if rs.servicio else 'N/A'}")
            print(f"     Fecha agendamiento: {rs.fecha_agendamiento}")
            print(f"     Hora inicio: {rs.hora_inicio}")
        print()

        # Verificar si es el mismo cliente
        if premio.cliente.id == reserva.cliente.id:
            print("✅ El cliente del premio COINCIDE con la reserva #3923")
        else:
            print("⚠️  ALERTA: El cliente del premio NO coincide con la reserva #3923")
            print(f"   Premio cliente: {premio.cliente.nombre}")
            print(f"   Reserva cliente: {reserva.cliente.nombre}")
        print()

    except VentaReserva.DoesNotExist:
        print("  ❌ No se encontró la reserva #3923")
        print()

    # Todas las reservas del cliente
    print(f"📊 HISTORIAL COMPLETO DEL CLIENTE: {premio.cliente.nombre}")
    cliente = premio.cliente
    todas_reservas = VentaReserva.objects.filter(cliente=cliente).order_by('fecha_reserva')
    print(f"  Total reservas: {todas_reservas.count()}")
    print()

    for i, r in enumerate(todas_reservas, 1):
        print(f"  {i}. Reserva #{r.id}")
        print(f"     Fecha reserva: {r.fecha_reserva}")
        print(f"     Estado: {r.estado_reserva}")
        # Servicios
        servicios = r.reservaservicios.all().order_by('fecha_agendamiento')
        for rs in servicios:
            print(f"     - Servicio: {rs.fecha_agendamiento} {rs.hora_inicio} - {rs.servicio.nombre if rs.servicio else 'N/A'}")
        print()

    # Servicios históricos
    from ventas.services.crm_service import CRMService
    datos_360 = CRMService.get_customer_360(cliente.id)
    print(f"📈 MÉTRICAS DEL CLIENTE:")
    print(f"  Servicios históricos: {datos_360['metricas']['servicios_historicos']}")
    print(f"  Total servicios: {datos_360['metricas']['total_servicios']}")
    print(f"  Gasto total: ${datos_360['metricas']['gasto_total']:,.0f}")
    print()

    # Fecha objetivo que debió procesar
    from datetime import timedelta
    hoy = timezone.now().date()
    fecha_objetivo = hoy - timedelta(days=3)
    print(f"🗓️  FECHAS:")
    print(f"  Hoy: {hoy}")
    print(f"  Fecha objetivo (hace 3 días): {fecha_objetivo}")
    print(f"  El cron busca servicios con fecha_agendamiento = {fecha_objetivo}")
    print()

    # Verificar si algún servicio coincide
    servicios_objetivo = ReservaServicio.objects.filter(
        venta_reserva__cliente=cliente,
        fecha_agendamiento=fecha_objetivo
    )
    if servicios_objetivo.exists():
        print(f"✅ SÍ hay servicios en la fecha objetivo ({fecha_objetivo}):")
        for rs in servicios_objetivo:
            print(f"   - Reserva #{rs.venta_reserva_id}: {rs.servicio.nombre if rs.servicio else 'N/A'}")
    else:
        print(f"❌ NO hay servicios en la fecha objetivo ({fecha_objetivo})")
    print()

    # Conclusión
    print("=" * 80)
    print("🎯 ANÁLISIS:")
    print("=" * 80)
    primer_servicio = ReservaServicio.objects.filter(
        venta_reserva__cliente=cliente
    ).order_by('fecha_agendamiento', 'id').first()

    if primer_servicio:
        print(f"  Primer servicio del cliente: {primer_servicio.fecha_agendamiento}")
        dias_desde_primer_servicio = (hoy - primer_servicio.fecha_agendamiento).days
        print(f"  Días desde primer servicio: {dias_desde_primer_servicio}")

        if primer_servicio.fecha_agendamiento == fecha_objetivo:
            print(f"  ✅ El primer servicio SÍ fue hace 3 días → CORRECTO")
        else:
            print(f"  ⚠️  El primer servicio NO fue hace 3 días")
            print(f"     Esperado: {fecha_objetivo}")
            print(f"     Real: {primer_servicio.fecha_agendamiento}")
            print(f"     Diferencia: {(fecha_objetivo - primer_servicio.fecha_agendamiento).days} días")

    print("=" * 80 + "\n")

except ClientePremio.DoesNotExist:
    print("❌ No se encontró el premio #74")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
