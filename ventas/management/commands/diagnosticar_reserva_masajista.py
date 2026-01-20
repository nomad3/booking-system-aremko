"""
Comando para diagnosticar por qué ciertas reservas no aparecen en los listados de pagos a masajistas
"""
from django.core.management.base import BaseCommand
from ventas.models import VentaReserva, ReservaServicio, Proveedor


class Command(BaseCommand):
    help = 'Diagnostica reservas específicas de masajistas'

    def add_arguments(self, parser):
        parser.add_argument('reserva_ids', nargs='+', type=int, help='IDs de reservas a diagnosticar')

    def handle(self, *args, **options):
        reserva_ids = options['reserva_ids']

        self.stdout.write(self.style.SUCCESS('=== DIAGNÓSTICO DE RESERVAS ===\n'))

        for reserva_id in reserva_ids:
            self.stdout.write(f'\n--- RESERVA #{reserva_id} ---')

            try:
                venta_reserva = VentaReserva.objects.get(id=reserva_id)

                self.stdout.write(f'\n✓ VentaReserva encontrada:')
                self.stdout.write(f'  ID: {venta_reserva.id}')
                self.stdout.write(f'  Cliente: {venta_reserva.cliente.nombre if venta_reserva.cliente else "Sin cliente"}')
                self.stdout.write(f'  Estado Reserva: {venta_reserva.estado_reserva}')
                self.stdout.write(f'  Estado Pago: {venta_reserva.estado_pago}')
                self.stdout.write(f'  Fecha Creación: {venta_reserva.fecha_creacion}')
                self.stdout.write(f'  Total: ${venta_reserva.total}')
                self.stdout.write(f'  Pagado: ${venta_reserva.pagado}')
                self.stdout.write(f'  Saldo Pendiente: ${venta_reserva.saldo_pendiente}')

                # Buscar servicios asociados
                servicios = ReservaServicio.objects.filter(venta_reserva=venta_reserva)
                self.stdout.write(f'\n  Servicios asociados: {servicios.count()}')

                for servicio in servicios:
                    self.stdout.write(f'\n  --- ReservaServicio #{servicio.id} ---')
                    self.stdout.write(f'    Servicio: {servicio.servicio.nombre if servicio.servicio else "SIN SERVICIO"}')
                    self.stdout.write(f'    Fecha: {servicio.fecha_agendamiento}')
                    self.stdout.write(f'    Hora: {servicio.hora_inicio}')
                    self.stdout.write(f'    Proveedor Asignado: {servicio.proveedor_asignado.nombre if servicio.proveedor_asignado else "NO ASIGNADO ❌"}')
                    self.stdout.write(f'    Cantidad Personas: {servicio.cantidad_personas}')
                    if servicio.servicio:
                        self.stdout.write(f'    Precio Base: ${servicio.servicio.precio_base}')

                    # Verificar si es masajista
                    if servicio.proveedor_asignado:
                        proveedor = servicio.proveedor_asignado
                        self.stdout.write(f'    Es Masajista: {proveedor.es_masajista}')
                        self.stdout.write(f'    % Comisión: {proveedor.porcentaje_comision}%')

                        # Verificar condiciones para aparecer en listados
                        self.stdout.write(f'\n    CONDICIONES PARA LISTADO:')
                        if proveedor.es_masajista:
                            self.stdout.write(self.style.SUCCESS(f'      ✓ Es masajista'))
                        else:
                            self.stdout.write(self.style.ERROR(f'      ✗ NO es masajista'))

                        if venta_reserva.estado_pago == 'pagado':
                            self.stdout.write(self.style.SUCCESS(f'      ✓ Estado pago = pagado'))
                        else:
                            self.stdout.write(self.style.WARNING(f'      ⚠ Estado pago = {venta_reserva.estado_pago} (debe ser "pagado")'))

                        if venta_reserva.estado_reserva != 'cancelada':
                            self.stdout.write(self.style.SUCCESS(f'      ✓ Reserva NO cancelada'))
                        else:
                            self.stdout.write(self.style.ERROR(f'      ✗ Reserva CANCELADA'))
                    else:
                        self.stdout.write(self.style.ERROR(f'\n    ✗ PROBLEMA: No tiene proveedor asignado'))
                        self.stdout.write(f'    Esta es la razón por la que NO aparece en los listados')

                # Resumen del problema
                self.stdout.write(f'\n  DIAGNÓSTICO FINAL:')
                sin_proveedor = servicios.filter(proveedor_asignado__isnull=True).count()
                if sin_proveedor > 0:
                    self.stdout.write(self.style.ERROR(f'    ✗ {sin_proveedor} servicio(s) sin proveedor asignado'))

                no_masajista = servicios.filter(proveedor_asignado__isnull=False, proveedor_asignado__es_masajista=False).count()
                if no_masajista > 0:
                    self.stdout.write(self.style.WARNING(f'    ⚠ {no_masajista} servicio(s) con proveedor que NO es masajista'))

                if venta_reserva.estado_pago != 'pagado':
                    self.stdout.write(self.style.WARNING(f'    ⚠ Estado de pago: {venta_reserva.estado_pago} (debe ser "pagado")'))

                if venta_reserva.estado_reserva == 'cancelada':
                    self.stdout.write(self.style.ERROR(f'    ✗ Reserva cancelada'))

            except VentaReserva.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'✗ VentaReserva #{reserva_id} NO EXISTE'))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))

        self.stdout.write(self.style.SUCCESS('\n\n=== FIN DEL DIAGNÓSTICO ===\n'))

        # Mostrar todas las masajistas disponibles
        self.stdout.write('\nMASAJISTAS DISPONIBLES EN EL SISTEMA:')
        masajistas = Proveedor.objects.filter(es_masajista=True).order_by('nombre')
        for m in masajistas:
            self.stdout.write(f'  - {m.nombre} (ID: {m.id})')
