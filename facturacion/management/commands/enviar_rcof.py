"""Genera y envía el Registro de Ventas Diarias (ex-RCOF) del día.

El SII lo pide junto al set de boletas: «Enviar al SII el Set de Boletas
generado y el Reporte de Consumo de Folios (RCOF) asociado». Sin él la
certificación no avanza, porque lo que quieren verificar es justamente la
capacidad de generarlo.

Por defecto SOLO genera y muestra: enviar es irreversible y queda para cuando
el XML se vea bien.

Uso:
  python manage.py enviar_rcof                 # genera y muestra
  python manage.py enviar_rcof --enviar        # además lo manda al SII
  python manage.py enviar_rcof --fecha 2026-08-31
"""
import datetime

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client


class Command(BaseCommand):
    help = 'Genera (y opcionalmente envía) el consumo de folios del día.'

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default='',
                            help='Día a reportar (AAAA-MM-DD). Por defecto, hoy.')
        parser.add_argument('--enviar', action='store_true',
                            help='Enviar al SII (sin esto solo muestra el XML).')
        parser.add_argument('--secuencia', type=int, default=1,
                            help='Número de envío del día (1 el primero).')
        parser.add_argument('--solo-set', action='store_true',
                            help='Reportar solo las boletas del set de pruebas.')

    def handle(self, *args, **opts):
        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        config = ConfiguracionFacturacion.get()
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()

        fecha = (datetime.date.fromisoformat(opts['fecha']) if opts['fecha']
                 else datetime.date.today())

        qs = BoletaElectronica.objects.filter(ambiente='certificacion').exclude(estado='error')
        if opts['solo_set']:
            qs = qs.filter(caso_set__startswith='CASO')
        # Las boletas emitidas ESE día: el consumo de folios es diario.
        boletas = [b for b in qs.order_by('folio')
                   if b.xml_dte and f'<FchEmis>{fecha:%Y-%m-%d}</FchEmis>' in b.xml_dte]
        if not boletas:
            raise CommandError(f'No hay boletas de certificación emitidas el {fecha}.')

        self.stdout.write(f'Reportando {len(boletas)} boleta(s) del {fecha}: '
                          f'folios {[b.folio for b in boletas]}')
        rvd = simpleapi_client.generar_rvd(
            [b.xml_dte for b in boletas], cert_bytes, cert_password, config,
            fecha, secuencia=opts['secuencia'])
        self.stdout.write('--- RVD (primeros 1200 caracteres) ---')
        self.stdout.write(' '.join(rvd.split())[:1200])

        if not opts['enviar']:
            self.stdout.write('--- generado, NO enviado (usa --enviar) ---')
            return

        ambiente_num = 0 if config.ambiente == 'certificacion' else 1
        resp = simpleapi_client.enviar_sobre(
            rvd, cert_bytes, cert_password, config, ambiente_num,
            tipo=simpleapi_client.TIPO_ENVIO_RVD)
        self.stdout.write(f'ENVÍO RVD: {resp}')
