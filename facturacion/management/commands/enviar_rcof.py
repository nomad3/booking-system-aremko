"""Genera, firma, valida y (si se pide) envía el consumo de folios del día.

El SII lo exige junto al set de boletas: «Enviar al SII el Set de Boletas
generado y el Reporte de Consumo de Folios (RCOF) asociado», y dice que el
plazo es de 24 horas «puesto que se pretende verificar la capacidad de
generación del RCOF».

Por defecto reporta las boletas del día que el SII efectivamente RECIBIÓ (las
que tienen trackId): así el reporte cuadra con lo que ellos ven. Y por defecto
NO envía: primero se mira el XML.

Uso:
  python manage.py enviar_rcof                  # genera, firma, valida, muestra
  python manage.py enviar_rcof --enviar         # además lo manda al SII
  python manage.py enviar_rcof --fecha 2026-08-31 --secuencia 2
"""
import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import rcof_builder, simpleapi_client

XSD = Path('/app/docs/certificacion_sii/ConsumoFolio_v10.xsd')


class Command(BaseCommand):
    help = 'Genera, firma y valida el consumo de folios del día (RVD/ex-RCOF).'

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default='')
        parser.add_argument('--secuencia', type=int, default=1)
        parser.add_argument('--enviar', action='store_true')
        parser.add_argument('--todas', action='store_true',
                            help='Incluir también boletas del día sin enviar al SII.')
        parser.add_argument('--ambiente', type=str, default='',
                            help='certificacion | produccion. Por defecto, el de '
                                 'la configuración (que puede seguir en simulado).')

    def handle(self, *args, **opts):
        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        config = ConfiguracionFacturacion.get()
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        fecha = (datetime.date.fromisoformat(opts['fecha']) if opts['fecha']
                 else timezone.localdate())

        ambiente = opts['ambiente'] or config.ambiente
        qs = (BoletaElectronica.objects.filter(ambiente=ambiente)
              .exclude(estado='error'))
        if not opts['todas']:
            qs = qs.exclude(track_id__isnull=True).exclude(track_id='')
        boletas = [b for b in qs.order_by('folio')
                   if b.xml_dte and f'<FchEmis>{fecha:%Y-%m-%d}</FchEmis>' in b.xml_dte]
        if not boletas:
            # El error tiene que decir DÓNDE buscó: la primera vez falló porque
            # la configuración seguía en «simulado» y las boletas del set viven
            # en «certificacion».
            hay = BoletaElectronica.objects.filter(ambiente=ambiente).count()
            raise CommandError(
                f'No hay boletas del {fecha} para reportar en ambiente '
                f'«{ambiente}» (hay {hay} boleta(s) en ese ambiente en total; '
                f'{"solo se miran las que tienen trackId" if not opts["todas"] else "se miraron todas"}). '
                f'Prueba --ambiente certificacion o --todas.')
        self.stdout.write(f'Folios del {fecha}: {[b.folio for b in boletas]} '
                          f'(total ${sum(int(b.monto_total or 0) for b in boletas):,})'
                          .replace(',', '.'))

        sin_firma, doc_id = rcof_builder.construir_consumo_folios(
            config, fecha, boletas, secuencia=opts['secuencia'],
            timestamp=timezone.localtime())
        xml = rcof_builder.firmar(sin_firma, doc_id, cert_bytes, cert_password)

        # Compuerta: el XML se valida contra el esquema oficial ANTES de salir.
        from lxml import etree
        if not XSD.exists():
            raise CommandError(f'Falta el XSD en {XSD}')
        schema = etree.XMLSchema(etree.parse(str(XSD)))
        arbol = etree.fromstring(xml.encode('ISO-8859-1', errors='replace'))
        if not schema.validate(arbol):
            self.stdout.write(f'VALIDACIÓN: FALLA ({len(schema.error_log)} errores)')
            for e in schema.error_log:
                self.stdout.write(f'--- línea {e.line}: {e.message}')
            raise CommandError('El consumo de folios no valida: no se envía.')
        self.stdout.write('VALIDACIÓN: OK (0 errores)')
        self.stdout.write('--- RCOF ---')
        self.stdout.write(' '.join(xml.split())[:900])

        if not opts['enviar']:
            self.stdout.write('--- generado y válido, NO enviado (usa --enviar) ---')
            return

        ambiente_num = 0 if ambiente == 'certificacion' else 1
        resp = simpleapi_client.enviar_sobre(
            xml, cert_bytes, cert_password, config, ambiente_num,
            tipo=simpleapi_client.TIPO_ENVIO_RVD)
        self.stdout.write(f'ENVÍO RCOF: {resp}')
