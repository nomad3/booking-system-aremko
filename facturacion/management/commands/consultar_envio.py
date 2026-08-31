"""Consulta el estado de un envío al SII por trackId (P-16, certificación).

Cierra el ciclo del set de pruebas: `ejecutar_set_pruebas` deja el trackId
en las boletas; este comando le pregunta al SII (vía SimpleAPI) si el envío
fue ACEPTADO — el dato que habilita declarar el avance de la certificación.

Uso:
  python manage.py consultar_envio --trackid 32032105
  python manage.py consultar_envio            # usa el trackId de las boletas del set
"""
from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client


class Command(BaseCommand):
    help = 'Consulta al SII el estado de un envío por trackId (vía SimpleAPI).'

    def add_arguments(self, parser):
        parser.add_argument('--trackid', type=int, default=None,
                            help='TrackId a consultar (default: el del set de pruebas).')

    def handle(self, *args, **opts):
        config = ConfiguracionFacturacion.get()
        track_id = opts['trackid']
        if track_id is None:
            boleta = (BoletaElectronica.objects
                      .filter(caso_set__startswith='CASO', track_id__isnull=False)
                      .exclude(track_id='').order_by('-id').first())
            if boleta is None:
                raise CommandError('No hay boletas del set con trackId; pásalo con --trackid.')
            track_id = int(boleta.track_id)

        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales (SIMPLEAPI_API_KEY / SII_CERT_*).')
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()

        ambiente_num = 0 if config.ambiente != 'produccion' else 1
        self.stdout.write(f'Consultando trackId={track_id} '
                          f'(ambiente={"cert" if ambiente_num == 0 else "prod"})...')
        r = simpleapi_client.consultar_estado_envio(
            track_id, cert_bytes, cert_password, config, ambiente_num)
        self.stdout.write(f'RESPUESTA: {r}')
