"""Qué medios de pago generan boleta y cuáles no (el interruptor anti doble boleteo)."""
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from facturacion.models import MedioPago


class Command(BaseCommand):
    help = 'Lista los medios de pago y su switch genera_boleta.'

    def add_arguments(self, parser):
        parser.add_argument('--ejemplos', action='store_true',
                            help='Muestra 3 pagos recientes de cada medio.')

    def handle(self, *args, **opts):
        from datetime import date, timedelta

        from ventas.models import Pago

        desde = date.today() - timedelta(days=60)
        uso = {r['metodo_pago']: r for r in Pago.objects
               .filter(fecha_pago__gte=desde)
               .values('metodo_pago')
               .annotate(n=Count('id'), total=Sum('monto'))}
        self.stdout.write('MEDIO DE PAGO                       BOLETEA   uso 60 días')
        for m in MedioPago.objects.all().order_by('-genera_boleta', 'nombre'):
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
