"""Imprime la Referencia REAL de cada boleta del set (P-16 forense).

El validador dice que el XML trae <TpoDocRef> aunque nuestro input ya no lo
manda. Esto mira el XML tal como lo devolvió SimpleAPI: si el campo sigue
ahí, el que lo agrega es el proveedor, no nosotros.
"""
from django.core.management.base import BaseCommand

from facturacion.models import BoletaElectronica


class Command(BaseCommand):
    help = 'Muestra el bloque <Referencia> de cada boleta del set.'

    def handle(self, *args, **opts):
        boletas = (BoletaElectronica.objects
                   .filter(caso_set__startswith='CASO').order_by('folio'))
        if not boletas:
            self.stdout.write('No hay boletas del set.')
            return
        for b in boletas:
            xml = b.xml_dte or ''
            if '<Referencia>' in xml:
                bloque = xml.split('<Referencia>')[1].split('</Referencia>')[0]
                bloque = ' '.join(bloque.split())
            else:
                bloque = 'SIN REFERENCIA'
            self.stdout.write(f'FOLIO {b.folio} [{b.caso_set}] :: {bloque}')
