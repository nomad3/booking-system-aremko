"""
Comando para analizar las ventas de un cliente específico
"""
from django.core.management.base import BaseCommand
from ventas.models import Cliente, VentaReserva
from django.db.models import Sum


class Command(BaseCommand):
    help = 'Analiza las ventas de un cliente para entender su gasto total'

    def add_arguments(self, parser):
        parser.add_argument('--cliente-id', type=int, required=True, help='ID del cliente a analizar')

    def handle(self, *args, **options):
        cliente_id = options['cliente_id']

        try:
            cliente = Cliente.objects.get(id=cliente_id)
        except Cliente.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'❌ Cliente #{cliente_id} no existe'))
            return

        self.stdout.write(self.style.SUCCESS('=' * 100))
        self.stdout.write(self.style.SUCCESS(f'ANÁLISIS DE VENTAS - CLIENTE #{cliente_id}: {cliente.nombre}'))
        self.stdout.write(self.style.SUCCESS('=' * 100))

        # Todas las ventas
        todas_ventas = cliente.ventareserva_set.all().order_by('-fecha_reserva')
        self.stdout.write(f'\n📊 Total de ventas/reservas: {todas_ventas.count()}')

        # Ventas por estado
        self.stdout.write(f'\n📋 Ventas por Estado de Pago:')
        for estado in ['pagado', 'parcial', 'pendiente']:
            ventas_estado = todas_ventas.filter(estado_pago=estado)
            total_estado = ventas_estado.aggregate(total=Sum('total'))['total'] or 0
            self.stdout.write(f'   {estado.upper()}: {ventas_estado.count()} ventas = ${float(total_estado):,.0f}')

        # Detalle de cada venta
        self.stdout.write(f'\n📝 Detalle de Ventas (ordenadas por fecha):')
        self.stdout.write('-' * 100)
        self.stdout.write(f'{"ID":<8} {"Fecha":<12} {"Estado Pago":<15} {"Total":<15} {"Pagado":<15} {"Saldo":<15}')
        self.stdout.write('-' * 100)

        for venta in todas_ventas[:20]:  # Mostrar últimas 20
            self.stdout.write(
                f'{venta.id:<8} '
                f'{venta.fecha_reserva.strftime("%Y-%m-%d"):<12} '
                f'{venta.estado_pago:<15} '
                f'${float(venta.total):>13,.0f} '
                f'${float(venta.pagado):>13,.0f} '
                f'${float(venta.saldo_pendiente):>13,.0f}'
            )

        if todas_ventas.count() > 20:
            self.stdout.write(f'\n... y {todas_ventas.count() - 20} ventas más')

        # Cálculo actual (solo pagado/parcial)
        ventas_pagadas = todas_ventas.filter(estado_pago__in=['pagado', 'parcial'])
        gasto_actual = ventas_pagadas.aggregate(total=Sum('total'))['total'] or 0

        self.stdout.write(f'\n💰 Cálculo de Gasto Total:')
        self.stdout.write(f'   Ventas pagadas/parciales: {ventas_pagadas.count()}')
        self.stdout.write(f'   Gasto total (método actual): ${float(gasto_actual):,.0f}')
        self.stdout.write(f'   Gasto total (método modelo): ${float(cliente.gasto_total()):,.0f}')

        # Identificar ventas negativas
        ventas_negativas = todas_ventas.filter(total__lt=0)
        if ventas_negativas.exists():
            self.stdout.write(f'\n⚠️  VENTAS CON TOTAL NEGATIVO:')
            for venta in ventas_negativas:
                self.stdout.write(
                    f'   Venta #{venta.id} - '
                    f'Fecha: {venta.fecha_reserva.strftime("%Y-%m-%d")} - '
                    f'Total: ${float(venta.total):,.0f} - '
                    f'Estado: {venta.estado_pago}'
                )

        self.stdout.write('\n' + '=' * 100)
        self.stdout.write(self.style.SUCCESS('FIN DEL ANÁLISIS'))
        self.stdout.write('=' * 100 + '\n')
