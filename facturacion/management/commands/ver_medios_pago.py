"""Qué medios de pago generan boleta y cuáles no (el interruptor anti doble boleteo)."""
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from facturacion.models import MedioPago


class Command(BaseCommand):
    help = 'Lista los medios de pago y su switch genera_boleta.'

    def add_arguments(self, parser):
        parser.add_argument('--ejemplos', action='store_true',
                            help='Muestra 3 pagos recientes de cada medio.')

    def add_arguments(self, parser):
        parser.add_argument('--desde', type=str, default='',
                            help='AAAA-MM-DD. Por defecto, los últimos 60 días.')
        parser.add_argument('--hasta', type=str, default='')
        parser.add_argument('--ejemplos', action='store_true',
                            help='3 pagos recientes de cada medio: con el nombre '
                                 'no basta para saber si fue tarjeta o transferencia.')
        parser.add_argument('--filtro', type=str, default='',
                            help='Parte del nombre del medio.')

    def handle(self, *args, **opts):
        from datetime import date, timedelta

        from ventas.models import Pago

        desde = (date.fromisoformat(opts['desde']) if opts['desde']
                 else date.today() - timedelta(days=60))
        hasta = (date.fromisoformat(opts['hasta']) if opts['hasta']
                 else date.today())
        pagos = Pago.objects.filter(fecha_pago__gte=desde,
                                    fecha_pago__lte=hasta)
        uso = {r['metodo_pago']: r for r in pagos
               .values('metodo_pago')
               .annotate(n=Count('id'), total=Sum('monto'))}
        self.stdout.write('MEDIO DE PAGO                       BOLETEA   uso 60 días')
        medios = MedioPago.objects.all().order_by('-genera_boleta', 'nombre')
        if opts['filtro']:
            medios = medios.filter(nombre__icontains=opts['filtro'])
        self.stdout.write(f'(desde {desde} hasta {hasta})')
        for m in medios:
            u = uso.get(m.codigo) or {}
            monto = f"${int(u.get('total') or 0):,}".replace(',', '.')
            self.stdout.write(
                f'  {m.nombre[:32]:<32} {"SÍ" if m.genera_boleta else "no":<7} '
                f'{u.get("n", 0):>4} pagos · {monto}   [{m.codigo}]')
            if opts['ejemplos'] and u.get('n'):
                for p in (Pago.objects.filter(metodo_pago=m.codigo,
                                              fecha_pago__gte=desde)
                          .select_related('venta_reserva__cliente')
                          .order_by('-fecha_pago')[:3]):
                    cli = getattr(getattr(p.venta_reserva, 'cliente', None),
                                  'nombre', '—')
                    self.stdout.write(
                        f'        · {p.fecha_pago:%d-%m} '
                        f'${int(p.monto):,}'.replace(',', '.')
                        + f' · reserva {getattr(p.venta_reserva, "id", "—")}'
                          f' · {str(cli)[:24]}')
