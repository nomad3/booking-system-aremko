"""Sonda: qué XML devuelve SimpleAPI para distintas formas de la Referencia.

El SII rechaza el sobre porque la boleta trae <TpoDocRef/> — un campo que en
tipo 39 no existe. No lo mandamos: lo agrega el proveedor. Y <CodRef> nos sale
como «4» cuando el instructivo pide «SET» textual.

Esto gasta UN folio por variante (no cinco) y muestra el bloque <Referencia>
tal como vuelve, para elegir la forma correcta antes de rehacer el set.

Uso: python manage.py probar_referencia
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import ConfiguracionFacturacion, RangoFolios
from facturacion.services import simpleapi_client

# Cada variante es una hipótesis sobre cómo hacer desaparecer <TpoDocRef>
# y cómo lograr <CodRef>SET</CodRef>.
VARIANTES = [
    ('A · TipoDocumento=null + CodRef "SET"',
     {"TipoDocumento": None, "CodigoReferencia": "SET", "RazonReferencia": "CASO-1"}),
    ('B · TipoDocumento=null + CodRef 4',
     {"TipoDocumento": None, "CodigoReferencia": 4, "RazonReferencia": "CASO-1"}),
    ('C · sin Referencias',
     None),
]


class Command(BaseCommand):
    help = 'Prueba formas de Referencia contra SimpleAPI (1 folio por variante).'

    def add_arguments(self, parser):
        parser.add_argument('--solo', type=str, default='',
                            help='Letras de variantes a probar, ej. "A" o "AB".')

    def handle(self, *args, **opts):
        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        config = ConfiguracionFacturacion.get()
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        hoy = datetime.date.today()

        rango = (RangoFolios.objects
                 .filter(tipo_dte=39, ambiente='certificacion').order_by('-id').first())
        if rango:
            self.stdout.write(f'CAF: rango {rango.folio_desde}-{rango.folio_hasta}, '
                              f'próximo {getattr(rango, "folio_actual", "?")}')

        filtro = (opts['solo'] or '').upper()
        for etiqueta, referencia in VARIANTES:
            if filtro and etiqueta[0] not in filtro:
                continue
            folio, rango = RangoFolios.asignar_folio(39, 'certificacion')
            if folio is None:
                raise CommandError('Sin folios CAF de certificación.')
            documento = simpleapi_client.construir_documento_boleta(
                config=config, folio=folio, fecha_emision=hoy,
                detalles=[{'nombre': 'Sonda referencia', 'cantidad': 1, 'precio': 1000}],
                cert_password=cert_password,
                referencias=[referencia] if referencia else None, tipo_dte=39)
            try:
                xml = simpleapi_client.generar_boleta(documento, cert_bytes, rango.caf_xml)
            except simpleapi_client.SimpleAPIError as exc:
                self.stdout.write(f'{etiqueta} (folio {folio}) :: ERROR {str(exc)[:300]}')
                continue
            if '<Referencia>' in xml:
                bloque = ' '.join(xml.split('<Referencia>')[1]
                                  .split('</Referencia>')[0].split())
            else:
                bloque = 'SIN BLOQUE Referencia'
            self.stdout.write(f'{etiqueta} (folio {folio}) :: {bloque}')
