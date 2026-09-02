"""Compara la firma que el SII ACEPTA (la de SimpleAPI en un DTE) con la nuestra.

El consumo de folios salió «Rechazado por Error en Firma». Las boletas del mismo
día pasaron, y esas las firma SimpleAPI: si hay una diferencia estructural entre
las dos firmas, está a la vista poniéndolas lado a lado.
"""
import datetime
import re

from django.core.management.base import BaseCommand
from django.utils import timezone

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import rcof_builder, simpleapi_client


def _firma(xml):
    m = re.search(r'<(?:\w+:)?Signature[\s>].*?</(?:\w+:)?Signature>', xml or '', re.S)
    return m.group(0) if m else ''


def _esqueleto(firma):
    """Solo la forma: etiquetas y algoritmos, sin los valores gigantes."""
    sin_valores = re.sub(r'>([A-Za-z0-9+/=\s]{40,})<', '>…<', firma)
    return ' '.join(sin_valores.split())


class Command(BaseCommand):
    help = 'Pone lado a lado la firma de SimpleAPI y la nuestra.'

    def handle(self, *args, **opts):
        b = (BoletaElectronica.objects.filter(ambiente='certificacion')
             .exclude(estado='error').order_by('-folio').first())
        self.stdout.write('=== FIRMA DE SIMPLEAPI (aceptada por el SII) ===')
        self.stdout.write(_esqueleto(_firma(b.xml_dte))[:1800] if b else '(sin boleta)')

        config = ConfiguracionFacturacion.get()
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        hoy = timezone.localdate()
        boletas = [x for x in BoletaElectronica.objects
                   .filter(ambiente='certificacion').exclude(estado='error')
                   .order_by('folio')
                   if x.xml_dte and f'<FchEmis>{hoy:%Y-%m-%d}</FchEmis>' in x.xml_dte]
        sin_firma, doc_id = rcof_builder.construir_consumo_folios(
            config, hoy, boletas, timestamp=timezone.localtime())
        nuestro = rcof_builder.firmar(sin_firma, doc_id, cert_bytes, cert_password)
        self.stdout.write('=== NUESTRA FIRMA (rechazada) ===')
        self.stdout.write(_esqueleto(_firma(nuestro))[:1800])

        # Autocomprobación: ¿la huella que firmamos sigue siendo la del
        # documento DESPUÉS de serializarlo? Si no, el error es nuestro y no
        # hace falta molestar al SII para saberlo.
        import base64
        import hashlib

        from lxml import etree

        arbol = etree.fromstring(nuestro.encode('ISO-8859-1', errors='replace'))
        doc = arbol.find('{http://www.sii.cl/SiiDte}DocumentoConsumoFolios')
        canon = etree.tostring(doc, method='c14n', exclusive=False, with_comments=False)
        recalculada = base64.b64encode(hashlib.sha1(canon).digest()).decode()
        escrita = arbol.find('.//{http://www.w3.org/2000/09/xmldsig#}DigestValue').text
        self.stdout.write(f'AUTOCHEQUEO huella escrita:     {escrita}')
        self.stdout.write(f'AUTOCHEQUEO huella recalculada: {recalculada}')
        self.stdout.write('AUTOCHEQUEO: ' +
                          ('COINCIDEN' if escrita == recalculada else 'NO COINCIDEN'))
