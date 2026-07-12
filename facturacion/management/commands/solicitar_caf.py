"""
Solicita un rango de folios (CAF) al SII vía SimpleAPI Folios y lo deja
cargado en RangoFolios, listo para timbrar boletas.

Uso:
  python manage.py solicitar_caf                  # 50 folios tipo 39, CERTIFICACIÓN
  python manage.py solicitar_caf --cantidad 1000  # producción usar --produccion
"""
import re

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import ConfiguracionFacturacion, RangoFolios
from facturacion.services import simpleapi_client


class Command(BaseCommand):
    help = 'Solicita folios CAF al SII (vía SimpleAPI) y los carga en RangoFolios.'

    def add_arguments(self, parser):
        parser.add_argument('--tipo', type=int, default=39,
                            help='Tipo de DTE (39 boleta afecta, 41 exenta). Default 39.')
        parser.add_argument('--cantidad', type=int, default=50,
                            help='Cantidad de folios a solicitar. Default 50.')
        parser.add_argument('--produccion', action='store_true',
                            help='Solicita folios REALES (default: ambiente de certificación).')

    def handle(self, *args, **options):
        config = ConfiguracionFacturacion.get()
        if not config.rut_emisor or not config.rut_firmante:
            raise CommandError("Configura rut_emisor y rut_firmante en Configuración de facturación.")
        if not simpleapi_client.credenciales_listas():
            raise CommandError("Faltan credenciales en el entorno (API key / certificado / clave).")

        ambiente = 'produccion' if options['produccion'] else 'certificacion'
        ambiente_num = 1 if options['produccion'] else 0
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()

        self.stdout.write(f"Solicitando {options['cantidad']} folios tipo {options['tipo']} "
                          f"en {ambiente}...")
        caf_xml = simpleapi_client.solicitar_folios(
            tipo_dte=options['tipo'],
            cantidad=options['cantidad'],
            cert_bytes=cert_bytes,
            cert_password=cert_password,
            rut_firmante=config.rut_firmante,
            rut_empresa=config.rut_emisor,
            ambiente_num=ambiente_num,
        )

        match = re.search(r'<RNG>\s*<D>(\d+)</D>\s*<H>(\d+)</H>', caf_xml)
        if not match:
            raise CommandError(f"No pude leer el rango del CAF: {caf_xml[:300]}")
        desde, hasta = int(match.group(1)), int(match.group(2))

        rango, creado = RangoFolios.objects.get_or_create(
            tipo_dte=options['tipo'], ambiente=ambiente, folio_desde=desde,
            defaults={'folio_hasta': hasta, 'folio_siguiente': desde,
                      'caf_xml': caf_xml, 'activo': True},
        )
        if not creado:
            self.stdout.write(self.style.WARNING("Ese rango ya estaba cargado — no se duplicó."))
        self.stdout.write(self.style.SUCCESS(
            f"CAF {ambiente} tipo {options['tipo']}: folios {desde}-{hasta} "
            f"({hasta - desde + 1} folios) listos."))
