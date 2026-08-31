"""Valida el sobre EnvioBoleta contra el XSD oficial del SII (P-16 forense).

El SII rechazó el sobre con LSX-00204 sin decir DÓNDE. Esto regenera el sobre
(vía SimpleAPI, sin enviar nada al SII) y lo valida con lxml contra
docs/certificacion_sii/EnvioBOLETA_v11.xsd: imprime CADA error con línea,
columna y el fragmento del XML alrededor — el dedo en la llaga.
"""
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client

XSD = Path('/app/docs/certificacion_sii/EnvioBOLETA_v11.xsd')


class Command(BaseCommand):
    help = 'Regenera el sobre del set y lo valida contra el XSD oficial.'

    def handle(self, *args, **opts):
        from lxml import etree

        if not XSD.exists():
            raise CommandError(f'No está el XSD en {XSD}')
        schema = etree.XMLSchema(etree.parse(str(XSD)))

        boletas = list(BoletaElectronica.objects
                       .filter(caso_set__startswith='CASO').order_by('folio'))
        if not boletas:
            raise CommandError('No hay boletas del set.')
        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        config = ConfiguracionFacturacion.get()
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        sobre = simpleapi_client.generar_sobre([b.xml_dte for b in boletas],
                                               cert_bytes, cert_password, config)

        doc = etree.fromstring(sobre.encode('ISO-8859-1', errors='replace'))
        ok = schema.validate(doc)
        self.stdout.write(f'VALIDACIÓN: {"OK" if ok else "FALLA"} '
                          f'({len(schema.error_log)} errores)')
        lineas = sobre.split('\n')
        for e in schema.error_log:
            self.stdout.write(f'--- línea {e.line} col {e.column}: {e.message}')
            ini = max(0, e.line - 2)
            for n in range(ini, min(len(lineas), e.line + 1)):
                marca = '>>' if n == e.line - 1 else '  '
                self.stdout.write(f'{marca} {n + 1}: {lineas[n][:180]}')
