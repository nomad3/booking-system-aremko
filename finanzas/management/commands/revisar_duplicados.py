# -*- coding: utf-8 -*-
"""Encuentra gastos que parecen estar contados dos veces (Jorge 2026-08-10).

Dos formas de duplicarse, y se informan por separado porque se arreglan
distinto:

  MISMA CUENTA  — casi siempre el mismo período cargado desde dos exports
                  distintos del banco. Sobra uno.
  CUENTAS DISTINTAS — el mismo cobro atribuido a dos medios de pago (Google
                  Ads figurando en la CuentaRUT y en la Visa). Sobra el que
                  no corresponde: hay que saber cuál es el bueno.

SOLO LECTURA por defecto. Para borrar hay que decir de QUÉ cuenta, porque
sin esa decisión el sistema no puede saber cuál de los dos es el bueno:

    python manage.py revisar_duplicados
    python manage.py revisar_duplicados --eliminar-de visa_2936
    python manage.py revisar_duplicados --eliminar-de visa_2936 --solo Google
"""
from collections import defaultdict
from datetime import date

from django.core.management.base import BaseCommand


def _clp(n):
    return '$' + format(int(n), ',d').replace(',', '.')


def firma_de(mov):
    """Lo que identifica al mismo cobro visto desde donde sea: día, monto y
    comercio. La glosa se normaliza porque cada fuente le pone su prefijo."""
    from finanzas.management.commands.detectar_recurrentes import (
        nombre_comercio)
    return (mov.fecha, int(mov.monto), nombre_comercio(mov.descripcion))


class Command(BaseCommand):
    help = 'Lista (y opcionalmente borra) gastos duplicados.'

    def add_arguments(self, parser):
        parser.add_argument('--desde', default='2026-07-01')
        parser.add_argument('--eliminar-de', default='',
                            help='Clave de la cuenta cuyos duplicados se borran.')
        parser.add_argument('--solo', default='',
                            help='Filtra por texto del comercio.')

    def handle(self, *args, **opts):
        from finanzas.models import MovimientoFinanciero

        desde = date.fromisoformat(opts['desde'])
        movs = (MovimientoFinanciero.objects
                .filter(clase='gasto', fecha__gte=desde)
                .select_related('cuenta', 'categoria').order_by('id'))

        grupos = defaultdict(list)
        for m in movs:
            grupos[firma_de(m)].append(m)

        repetidos = {k: v for k, v in grupos.items() if len(v) > 1}
        if opts['solo']:
            aguja = opts['solo'].upper()
            repetidos = {k: v for k, v in repetidos.items()
                         if aguja in k[2].upper()}

        misma, distintas = {}, {}
        for firma, lista in repetidos.items():
            cuentas = {m.cuenta_id for m in lista}
            (misma if len(cuentas) == 1 else distintas)[firma] = lista

        def _mostrar(titulo, grupo):
            total = sum(int(m.monto) for lista in grupo.values()
                        for m in lista[1:])
            self.stdout.write(f'\n=== {titulo}: {len(grupo)} casos · '
                              f'sobrante {_clp(total)} ===')
            for (fecha, monto, comercio), lista in sorted(
                    grupo.items(), key=lambda kv: -kv[0][1]):
                self.stdout.write(f'\n{fecha}  {comercio}  {_clp(monto)} '
                                  f'× {len(lista)}')
                for m in lista:
                    self.stdout.write(
                        f'   id {m.id:>6}  {m.cuenta.clave:<18} '
                        f'{m.fuente:<8} {(m.descripcion or "")[:52]}')
            return total

        sobra_misma = _mostrar('MISMA CUENTA (doble carga)', misma)
        sobra_dist = _mostrar('CUENTAS DISTINTAS (atribución)', distintas)
        self.stdout.write(f'\nSobrante total estimado: '
                          f'{_clp(sobra_misma + sobra_dist)}')

        objetivo = opts['eliminar_de']
        if not objetivo:
            self.stdout.write(
                '\nNada se borró. Para limpiar, repetir con '
                '--eliminar-de <clave_de_cuenta>: se borran los duplicados '
                'que estén en ESA cuenta, dejando siempre al menos uno.')
            return

        borrados = total = 0
        for lista in list(misma.values()) + list(distintas.values()):
            candidatos = [m for m in lista if m.cuenta.clave == objetivo]
            # Nunca dejar el grupo vacío: si todos son de esa cuenta, se
            # conserva el primero. Borrar el cobro entero sería peor que el
            # duplicado.
            sobrantes = (candidatos[1:] if len(candidatos) == len(lista)
                         else candidatos)
            for m in sobrantes:
                if m.traspaso_par_id:
                    self.stdout.write(f'   saltado id {m.id}: es parte de un '
                                      'traspaso, hay que deshacerlo a mano')
                    continue
                total += int(m.monto)
                borrados += 1
                m.delete()
        self.stdout.write(f'\nBorrados {borrados} movimientos de '
                          f'«{objetivo}» por {_clp(total)}.')
