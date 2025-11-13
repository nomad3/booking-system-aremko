"""
Management command para diagnosticar Premio #74
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from ventas.models import VentaReserva, ReservaServicio, ClientePremio
from ventas.services.crm_service import CRMService


class Command(BaseCommand):
    help = 'Diagnóstico del Premio #74 y Reserva #3923'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("🔍 DIAGNÓSTICO PREMIO #74"))
        self.stdout.write("=" * 80 + "\n")

        # Premio #74
        try:
            premio = ClientePremio.objects.get(id=74)
            self.stdout.write("📦 PREMIO #74:")
            self.stdout.write(f"  Cliente: {premio.cliente.nombre if premio.cliente else 'N/A'}")
            self.stdout.write(f"  Premio: {premio.premio.nombre if premio.premio else 'N/A'}")
            self.stdout.write(f"  Tipo: {premio.premio.tipo if premio.premio else 'N/A'}")
            self.stdout.write(f"  Fecha generación: {premio.fecha_generacion}")
            self.stdout.write(f"  Fecha ganado: {premio.fecha_ganado}")
            self.stdout.write(f"  Estado: {premio.estado}")
            self.stdout.write(f"  Gasto total al ganar: ${premio.gasto_total_al_ganar:,.0f}")
            self.stdout.write(f"  Tramo al ganar: {premio.tramo_al_ganar}")
            self.stdout.write("")

            # Buscar reserva 3923
            self.stdout.write("📋 RESERVA #3923:")
            try:
                reserva = VentaReserva.objects.get(id=3923)
                self.stdout.write(f"  Cliente: {reserva.cliente.nombre if reserva.cliente else 'N/A'}")
                self.stdout.write(f"  Fecha reserva: {reserva.fecha_reserva}")
                self.stdout.write(f"  Estado: {reserva.estado_reserva}")
                self.stdout.write(f"  Total: ${reserva.total:,.0f}")
                self.stdout.write("")

                # Servicios de la reserva
                self.stdout.write("🔧 SERVICIOS DE LA RESERVA #3923:")
                servicios = reserva.reservaservicios.all().order_by('fecha_agendamiento', 'hora_inicio')
                for i, rs in enumerate(servicios, 1):
                    self.stdout.write(f"  {i}. {rs.servicio.nombre if rs.servicio else 'N/A'}")
                    self.stdout.write(f"     Fecha agendamiento: {rs.fecha_agendamiento}")
                    self.stdout.write(f"     Hora inicio: {rs.hora_inicio}")
                self.stdout.write("")

                # Verificar si es el mismo cliente
                if premio.cliente.id == reserva.cliente.id:
                    self.stdout.write(self.style.SUCCESS("✅ El cliente del premio COINCIDE con la reserva #3923"))
                else:
                    self.stdout.write(self.style.WARNING("⚠️  ALERTA: El cliente del premio NO coincide con la reserva #3923"))
                    self.stdout.write(f"   Premio cliente: {premio.cliente.nombre}")
                    self.stdout.write(f"   Reserva cliente: {reserva.cliente.nombre}")
                self.stdout.write("")

            except VentaReserva.DoesNotExist:
                self.stdout.write(self.style.ERROR("  ❌ No se encontró la reserva #3923"))
                self.stdout.write("")

            # Todas las reservas del cliente
            self.stdout.write(f"📊 HISTORIAL COMPLETO DEL CLIENTE: {premio.cliente.nombre}")
            cliente = premio.cliente
            todas_reservas = VentaReserva.objects.filter(cliente=cliente).order_by('fecha_reserva')
            self.stdout.write(f"  Total reservas: {todas_reservas.count()}")
            self.stdout.write("")

            for i, r in enumerate(todas_reservas, 1):
                self.stdout.write(f"  {i}. Reserva #{r.id}")
                self.stdout.write(f"     Fecha reserva: {r.fecha_reserva}")
                self.stdout.write(f"     Estado: {r.estado_reserva}")
                # Servicios
                servicios = r.reservaservicios.all().order_by('fecha_agendamiento')
                for rs in servicios:
                    self.stdout.write(f"     - Servicio: {rs.fecha_agendamiento} {rs.hora_inicio} - {rs.servicio.nombre if rs.servicio else 'N/A'}")
                self.stdout.write("")

            # Servicios históricos
            datos_360 = CRMService.get_customer_360(cliente.id)
            self.stdout.write("📈 MÉTRICAS DEL CLIENTE:")
            self.stdout.write(f"  Servicios históricos: {datos_360['metricas']['servicios_historicos']}")
            self.stdout.write(f"  Total servicios: {datos_360['metricas']['total_servicios']}")
            self.stdout.write(f"  Gasto total: ${datos_360['metricas']['gasto_total']:,.0f}")
            self.stdout.write("")

            # Fecha objetivo que debió procesar
            hoy = timezone.now().date()
            fecha_objetivo = hoy - timedelta(days=3)
            self.stdout.write("🗓️  FECHAS:")
            self.stdout.write(f"  Hoy: {hoy}")
            self.stdout.write(f"  Fecha objetivo (hace 3 días): {fecha_objetivo}")
            self.stdout.write(f"  El cron busca servicios con fecha_agendamiento = {fecha_objetivo}")
            self.stdout.write("")

            # Verificar si algún servicio coincide
            servicios_objetivo = ReservaServicio.objects.filter(
                venta_reserva__cliente=cliente,
                fecha_agendamiento=fecha_objetivo
            )
            if servicios_objetivo.exists():
                self.stdout.write(self.style.SUCCESS(f"✅ SÍ hay servicios en la fecha objetivo ({fecha_objetivo}):"))
                for rs in servicios_objetivo:
                    self.stdout.write(f"   - Reserva #{rs.venta_reserva_id}: {rs.servicio.nombre if rs.servicio else 'N/A'}")
            else:
                self.stdout.write(self.style.WARNING(f"❌ NO hay servicios en la fecha objetivo ({fecha_objetivo})"))
            self.stdout.write("")

            # Conclusión
            self.stdout.write("=" * 80)
            self.stdout.write(self.style.SUCCESS("🎯 ANÁLISIS:"))
            self.stdout.write("=" * 80)
            primer_servicio = ReservaServicio.objects.filter(
                venta_reserva__cliente=cliente
            ).order_by('fecha_agendamiento', 'id').first()

            if primer_servicio:
                self.stdout.write(f"  Primer servicio del cliente: {primer_servicio.fecha_agendamiento}")
                dias_desde_primer_servicio = (hoy - primer_servicio.fecha_agendamiento).days
                self.stdout.write(f"  Días desde primer servicio: {dias_desde_primer_servicio}")

                if primer_servicio.fecha_agendamiento == fecha_objetivo:
                    self.stdout.write(self.style.SUCCESS("  ✅ El primer servicio SÍ fue hace 3 días → CORRECTO"))
                else:
                    self.stdout.write(self.style.WARNING("  ⚠️  El primer servicio NO fue hace 3 días"))
                    self.stdout.write(f"     Esperado: {fecha_objetivo}")
                    self.stdout.write(f"     Real: {primer_servicio.fecha_agendamiento}")
                    diferencia = (fecha_objetivo - primer_servicio.fecha_agendamiento).days
                    self.stdout.write(f"     Diferencia: {diferencia} días")

            self.stdout.write("=" * 80 + "\n")

        except ClientePremio.DoesNotExist:
            self.stdout.write(self.style.ERROR("❌ No se encontró el premio #74"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Error: {e}"))
            import traceback
            traceback.print_exc()
