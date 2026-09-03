"""
Envía al SII el sobre EnvioBOLETA con las boletas ya timbradas que aún no
se transmitieron (estado='generada'). Es la mitad que faltaba del F2: hoy
una boleta se genera y timbra al cobrar (con folio real del CAF), pero
timbrar no es lo mismo que transmitir — el SII exige además el envío del
sobre para que la boleta quede formalmente recibida.

Pensado para correr a diario (cron). Autorecuperable a propósito: si el
envío falla (SII caído, SimpleAPI caído), las boletas NO se tocan — siguen
en 'generada', así que la corrida de mañana las reintenta con el MISMO
folio ya timbrado. Pasarlas a 'error' aquí sería un error en sí mismo: la
próxima emisión de ese pago pediría un folio NUEVO y abandonaría el que ya
es válido — folio desperdiciado, no boleta perdida, pero desprolijo y
evitable.

Uso:
  python manage.py enviar_boletas_sii                            # usa config.ambiente
  python manage.py enviar_boletas_sii --ambiente certificacion    # forzado (pruebas)
  python manage.py enviar_boletas_sii --limite 50                 # tope por corrida
"""
from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client

AMBIENTE_NUM = {'certificacion': 0, 'produccion': 1}


class Command(BaseCommand):
    help = 'Envía al SII el sobre con las boletas timbradas y aún no transmitidas.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ambiente', choices=['certificacion', 'produccion'], default=None,
            help='Por defecto usa el ambiente ACTIVO en Configuración de facturación. '
                 'Forzar un valor es solo para probar sin depender del switch real.')
        parser.add_argument(
            '--limite', type=int, default=200,
            help='Tope de boletas por corrida (default 200 — freno de seguridad, '
                 'no un límite operativo: el volumen esperado es ~200/MES).')

    def handle(self, *args, **options):
        config = ConfiguracionFacturacion.get()
        ambiente = options['ambiente'] or config.ambiente

        if ambiente not in AMBIENTE_NUM:
            # 'simulado' (o cualquier otro valor futuro): nada que transmitir,
            # y sobre todo, nada que HABLE con SimpleAPI por error.
            self.stdout.write(f"Ambiente '{ambiente}' no transmite al SII. Nada que hacer.")
            return

        pendientes = list(
            BoletaElectronica.objects
            .filter(ambiente=ambiente, tipo_dte=39, estado='generada')
            .exclude(xml_dte='')
            .order_by('folio')[:options['limite']])

        if not pendientes:
            self.stdout.write(f"Sin boletas pendientes de envío en {ambiente}.")
            return

        if not simpleapi_client.credenciales_listas():
            raise CommandError("Faltan credenciales en el entorno "
                               "(SIMPLEAPI_API_KEY / SII_CERT_B64 / SII_CERT_PASSWORD).")

        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        self.stdout.write(f"Enviando {len(pendientes)} boleta(s) en {ambiente} "
                          f"(folios {pendientes[0].folio}-{pendientes[-1].folio})...")

        xmls = [b.xml_dte for b in pendientes]
        try:
            sobre = simpleapi_client.generar_sobre(xmls, cert_bytes, cert_password, config)
        except simpleapi_client.SimpleAPIError as exc:
            # Nada se tocó todavía: las boletas siguen 'generada'.
            raise CommandError(f"No se pudo armar el sobre: {exc}")

        try:
            resp = simpleapi_client.enviar_sobre(
                sobre, cert_bytes, cert_password, config,
                ambiente_num=AMBIENTE_NUM[ambiente], tipo=2)
        except simpleapi_client.SimpleAPIError as exc:
            raise CommandError(f"No se pudo enviar el sobre al SII: {exc}")

        if not resp.get('ok'):
            # El sobre se armó pero el SII no lo aceptó. A propósito NO se
            # marca 'error': ver el docstring — se reintenta tal cual mañana.
            raise CommandError(f"El SII no aceptó el sobre: {resp}")

        track = str(resp.get('trackId', '') or '')
        for boleta in pendientes:
            boleta.track_id = track
            boleta.estado = 'enviada'
            boleta.save(update_fields=['track_id', 'estado', 'actualizada_at'])

        self.stdout.write(self.style.SUCCESS(
            f"{len(pendientes)} boleta(s) enviada(s) — trackId={track} "
            f"estado={resp.get('estado', '')}"))
