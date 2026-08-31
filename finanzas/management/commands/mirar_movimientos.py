"""Sonda de solo lectura: qué hay registrado, tal como está.

Antes de reclasificar plata conviene mirarla. Este comando no escribe nada.

Uso:
  python manage.py mirar_movimientos --desde 2026-08-01 --hasta 2026-08-31
  python manage.py mirar_movimientos --texto retiro
  python manage.py mirar_movimientos --cuenta "Mercado" --desde 2026-08-10
"""
import datetime

from django.core.management.base import BaseCommand

from finanzas.models import CuentaFinanciera, MovimientoFinanciero


class Command(BaseCommand):
    help = 'Muestra movimientos financieros (solo lectura).'

    def add_arguments(self, parser):
        parser.add_argument('--desde', type=str, default='')
        parser.add_argument('--hasta', type=str, default='')
        parser.add_argument('--cuenta', type=str, default='',
                            help='Parte del nombre de la cuenta.')
        parser.add_argument('--texto', type=str, default='',
                            help='Parte de la descripción.')
        parser.add_argument('--limite', type=int, default=60)
        parser.add_argument('--cuentas', action='store_true',
                            help='Solo listar las cuentas y sus totales.')

    def handle(self, *args, **o):
        if o['cuentas']:
            self.stdout.write('CUENTAS:')
            for c in CuentaFinanciera.objects.all().order_by('nombre'):
                n = c.movimientos.count()
                self.stdout.write(f'  {c.id:>3} · {c.nombre:<34} {c.tipo:<12} '
                                  f'{n} movimiento(s)')
            return

        qs = MovimientoFinanciero.objects.select_related('cuenta', 'categoria',
                                                         'traspaso_par')
        if o['desde']:
            qs = qs.filter(fecha__gte=datetime.date.fromisoformat(o['desde']))
        if o['hasta']:
            qs = qs.filter(fecha__lte=datetime.date.fromisoformat(o['hasta']))
        if o['cuenta']:
            qs = qs.filter(cuenta__nombre__icontains=o['cuenta'])
        if o['texto']:
            qs = qs.filter(descripcion__icontains=o['texto'])

        qs = qs.order_by('fecha', 'id')[:o['limite']]
        self.stdout.write(f'{len(qs)} movimiento(s):')
        for m in qs:
            monto = f'${int(m.monto):,}'.replace(',', '.')
            par = f' ⇄ #{m.traspaso_par_id}' if m.traspaso_par_id else ''
            cat = m.categoria.nombre if m.categoria else '—'
            self.stdout.write(
                f'  #{m.id:<6} {m.fecha} {m.cuenta.nombre[:22]:<22} '
                f'{m.clase:<8} {m.sentido:<5} {monto:>12} · {cat[:22]:<22} '
                f'· {m.descripcion[:46]}{par}')
