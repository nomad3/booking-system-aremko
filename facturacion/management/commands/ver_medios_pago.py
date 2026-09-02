"""Qué medios de pago generan boleta y cuáles no (el interruptor anti doble boleteo)."""
from django.core.management.base import BaseCommand
from django.db.models import Count, Sum

from facturacion.models import MedioPago


class Command(BaseCommand):
    help = 'Lista los medios de pago y su switch genera_boleta.'

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
                f'{u.get("n", 0):>4} pagos · {monto}')
