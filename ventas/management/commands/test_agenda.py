"""
Management command to test and diagnose agenda operativa queries
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import datetime, time
from ventas.models import ReservaServicio, VentaReserva

class Command(BaseCommand):
    help = 'Test agenda operativa queries to diagnose issues'

    def handle(self, *args, **options):
        # Get current time in Chile timezone
        ahora = timezone.localtime(timezone.now())
        hoy = ahora.date()
        hora_actual = ahora.time()

        self.stdout.write(f"\n=== DIAGNÓSTICO AGENDA OPERATIVA ===")
        self.stdout.write(f"Fecha actual: {hoy}")
        self.stdout.write(f"Hora actual (Chile): {hora_actual.strftime('%H:%M')}")
        self.stdout.write(f"Timezone: {timezone.get_current_timezone()}")

        # Query all services for today
        self.stdout.write(f"\n=== TODOS LOS SERVICIOS DE HOY ===")
        todos_servicios = ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).select_related('servicio', 'venta_reserva__cliente')

        self.stdout.write(f"Total servicios encontrados: {todos_servicios.count()}")

        # Show first 10 services with details
        for servicio in todos_servicios[:10]:
            self.stdout.write(f"\nServicio ID: {servicio.id}")
            self.stdout.write(f"  - Nombre: {servicio.servicio.nombre if servicio.servicio else 'SIN SERVICIO'}")
            self.stdout.write(f"  - Fecha: {servicio.fecha_agendamiento}")
            self.stdout.write(f"  - Hora: {servicio.hora_inicio}")
            self.stdout.write(f"  - Cliente: {servicio.venta_reserva.cliente.nombre if servicio.venta_reserva and servicio.venta_reserva.cliente else 'SIN CLIENTE'}")
            self.stdout.write(f"  - Reserva ID: {servicio.venta_reserva.id if servicio.venta_reserva else 'SIN RESERVA'}")
            self.stdout.write(f"  - Estado reserva: {servicio.venta_reserva.estado_reserva if servicio.venta_reserva else 'N/A'}")

        # Filter excluding cancelled
        self.stdout.write(f"\n=== SERVICIOS NO CANCELADOS ===")
        servicios_activos = ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).select_related('servicio', 'venta_reserva__cliente')

        self.stdout.write(f"Total servicios no cancelados: {servicios_activos.count()}")

        # Filter from current time
        self.stdout.write(f"\n=== SERVICIOS DESDE HORA ACTUAL ({hora_actual.strftime('%H:%M')}) ===")
        servicios_pendientes = []
        for servicio in servicios_activos:
            try:
                servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()
                if servicio_hora >= hora_actual:
                    servicios_pendientes.append(servicio)
                    if len(servicios_pendientes) <= 5:
                        self.stdout.write(f"  - {servicio.hora_inicio}: {servicio.servicio.nombre} - Cliente: {servicio.venta_reserva.cliente.nombre}")
            except Exception as e:
                self.stdout.write(f"  ERROR procesando hora '{servicio.hora_inicio}': {e}")

        self.stdout.write(f"Total servicios pendientes: {len(servicios_pendientes)}")

        # Check unique reservation states
        self.stdout.write(f"\n=== ESTADOS DE RESERVA ÚNICOS ===")
        estados = set()
        for servicio in todos_servicios:
            if servicio.venta_reserva:
                estados.add(servicio.venta_reserva.estado_reserva)

        for estado in estados:
            count = todos_servicios.filter(venta_reserva__estado_reserva=estado).count()
            self.stdout.write(f"  - {estado}: {count} servicios")

        # Check if there are any NULL venta_reserva
        sin_reserva = todos_servicios.filter(venta_reserva__isnull=True).count()
        if sin_reserva > 0:
            self.stdout.write(f"\n⚠️  Hay {sin_reserva} servicios sin venta_reserva asociada")

        # Sample query as in the view
        self.stdout.write(f"\n=== QUERY EXACTO DE LA VISTA ===")
        servicios_vista = ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).select_related(
            'servicio',
            'venta_reserva__cliente'
        ).order_by('hora_inicio')

        self.stdout.write(f"Servicios según vista: {servicios_vista.count()}")

        if servicios_vista.exists():
            self.stdout.write("\nPrimeros 3 servicios:")
            for srv in servicios_vista[:3]:
                self.stdout.write(f"  {srv.hora_inicio} - {srv.servicio.nombre} - {srv.venta_reserva.cliente.nombre}")