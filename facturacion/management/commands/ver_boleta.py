"""Muestra los totales y el detalle de una boleta del set, tal como se enviaron.

El SII rechaza el CASO-5 con «Valor del Monto Total no coinciden con el del COF»
incluso en un día limpio, así que el problema está en el documento y no en el
contexto. Esto imprime lo que de verdad se le mandó.

Uso: python manage.py ver_boleta --folio 33
     python manage.py ver_boleta --caso CASO-5
"""
import re

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica


def _bloques(xml, etiqueta):
    return re.findall(rf'<{etiqueta}>(.*?)</{etiqueta}>', xml or '', re.S)


class Command(BaseCommand):
    help = 'Totales y detalle de una boleta del set.'

    def add_arguments(self, parser):
        parser.add_argument('--folio', type=int, default=None)
        parser.add_argument('--caso', type=str, default='')

    def handle(self, *args, **o):
        qs = BoletaElectronica.objects.filter(ambiente='certificacion')
        if o['folio']:
            qs = qs.filter(folio=o['folio'])
        if o['caso']:
            qs = qs.filter(caso_set=o['caso'])
        b = qs.order_by('-folio').first()
        if b is None:
            raise CommandError('No encontré esa boleta.')

        xml = b.xml_dte or ''
        self.stdout.write(f'FOLIO {b.folio} [{b.caso_set}] · guardado: neto '
                          f'{b.monto_neto} iva {b.monto_iva} total {b.monto_total}')
        for et in ('MntNeto', 'MntExe', 'IVA', 'TasaIVA', 'MntTotal', 'FchEmis',
                   'IndServicio'):
            for v in _bloques(xml, et):
                self.stdout.write(f'  {et}: {v.strip()}')
        for i, det in enumerate(_bloques(xml, 'Detalle'), start=1):
            plano = ' '.join(det.split())
            self.stdout.write(f'  --- Detalle {i}: {plano[:300]}')
