"""
Ejecuta el SET DE PRUEBAS de boleta electrónica del SII (certificación P-16).

Los 5 casos están transcritos EXACTOS desde docs/certificacion_sii/Set_Prueba_BE.txt
(el SII exige informar los caracteres tal cual). Cada boleta referencia su caso
(TipoDocumento=SET, RazonReferencia=CASO-N) como pide el instructivo.

Flujo: por cada caso asigna folio del CAF de certificación → genera y timbra la
boleta vía SimpleAPI → guarda BoletaElectronica (sin pago, caso_set=CASO-N).
Luego arma el sobre EnvioBoleta y lo envía al ambiente de certificación del SII
(trackId queda en cada boleta).

Uso:
  python manage.py ejecutar_set_pruebas                # genera + envía
  python manage.py ejecutar_set_pruebas --solo-generar # sin envío al SII
Idempotente: los casos ya generados no se re-timbran (usa --regenerar para forzar).
"""
import time

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from facturacion.models import (BoletaElectronica, ConfiguracionFacturacion,
                                RangoFolios)
from facturacion.services import simpleapi_client

CASOS = [
    ('CASO-1', [
        {'nombre': 'Cambio de aceite', 'cantidad': 1, 'precio': 19900},
        {'nombre': 'Alineacion y balanceo', 'cantidad': 1, 'precio': 9900},
    ]),
    ('CASO-2', [
        {'nombre': 'Papel de regalo', 'cantidad': 17, 'precio': 120},
    ]),
    ('CASO-3', [
        {'nombre': 'Sandwic', 'cantidad': 2, 'precio': 1500},
        {'nombre': 'Bebida', 'cantidad': 2, 'precio': 550},
    ]),
    ('CASO-4', [
        {'nombre': 'item afecto 1', 'cantidad': 8, 'precio': 1590},
        {'nombre': 'item exento 2', 'cantidad': 2, 'precio': 1000, 'exento': True},
    ]),
    ('CASO-5', [
        {'nombre': 'Arroz', 'cantidad': 5, 'precio': 700, 'unidad': 'Kg'},
    ]),
]

TASA_IVA = 1.19


def _totales(detalles):
    afecto = sum(int(round(d.get('cantidad', 1) * d['precio']))
                 for d in detalles if not d.get('exento'))
    exento = sum(int(round(d.get('cantidad', 1) * d['precio']))
                 for d in detalles if d.get('exento'))
    neto = int(round(afecto / TASA_IVA))
    iva = afecto - neto
    return neto, iva, afecto + exento


class Command(BaseCommand):
    help = 'Ejecuta el set de pruebas de boleta electrónica en el ambiente de certificación.'

    def add_arguments(self, parser):
        parser.add_argument('--solo-generar', action='store_true',
                            help='Genera y timbra las boletas pero NO envía el sobre al SII.')
        parser.add_argument('--regenerar', action='store_true',
                            help='Vuelve a timbrar casos ya generados (usa folios nuevos).')

    def handle(self, *args, **options):
        config = ConfiguracionFacturacion.get()
        if not simpleapi_client.credenciales_listas():
            raise CommandError("Faltan credenciales en el entorno.")
        if not (config.rut_emisor and config.rut_firmante and config.razon_social
                and config.giro_boleta and config.direccion):
            raise CommandError("Completa los datos del emisor en Configuración de facturación.")
        if not config.fecha_resolucion:
            raise CommandError("Configura fecha_resolucion (fecha de la postulación aceptada).")

        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        hoy = timezone.localdate()
        boletas = []

        for numero, (caso, detalles) in enumerate(CASOS, start=1):
            existente = (BoletaElectronica.objects
                         .filter(caso_set=caso, ambiente='certificacion')
                         .exclude(estado='error').first())
            if existente and existente.xml_dte and not options['regenerar']:
                self.stdout.write(f"{caso}: ya generado (folio {existente.folio}) — se reutiliza.")
                boletas.append(existente)
                continue

            folio, rango = RangoFolios.asignar_folio(39, 'certificacion')
            if folio is None:
                raise CommandError("Sin folios CAF de certificación: corre `solicitar_caf` primero.")

            referencias = [{
                "TipoDocumento": "SET",
                "FolioReferencia": str(numero),
                "FechaDocumentoReferencia": hoy.strftime('%Y-%m-%d'),
                "RazonReferencia": caso,
            }]
            documento = simpleapi_client.construir_documento_boleta(
                config=config, folio=folio, fecha_emision=hoy,
                detalles=detalles, cert_password=cert_password,
                referencias=referencias, tipo_dte=39)
            try:
                # El CAF debe ser el MISMO rango del que salió el folio.
                xml = simpleapi_client.generar_boleta(documento, cert_bytes, rango.caf_xml)
            except simpleapi_client.SimpleAPIError as exc:
                raise CommandError(f"{caso}: error al generar — {exc}")

            neto, iva, total = _totales(detalles)
            boleta = BoletaElectronica.objects.create(
                pago=None, tipo_dte=39, ambiente='certificacion', folio=folio,
                monto_total=total, monto_neto=neto, monto_iva=iva,
                glosa=f"SET SII {caso}", caso_set=caso, estado='generada',
                xml_dte=xml, emitida_at=timezone.now())
            boletas.append(boleta)
            self.stdout.write(self.style.SUCCESS(
                f"{caso}: boleta timbrada folio {folio} (total ${total:,})".replace(',', '.')))
            time.sleep(0.5)  # rate limit 3/s

        if options['solo_generar']:
            self.stdout.write("Solo generación — no se envió el sobre (--solo-generar).")
            return

        self.stdout.write("Generando sobre EnvioBoleta...")
        xmls = [b.xml_dte for b in boletas]
        sobre = simpleapi_client.generar_sobre(xmls, cert_bytes, cert_password, config)

        self.stdout.write("Enviando al SII (ambiente certificación)...")
        resp = simpleapi_client.enviar_sobre(sobre, cert_bytes, cert_password,
                                             config, ambiente_num=0, tipo=2)
        track = str(resp.get('trackId', '') or '')
        ok = resp.get('ok')
        estado = resp.get('estado', '')
        for boleta in boletas:
            boleta.track_id = track
            boleta.estado = 'enviada' if ok else 'error'
            if not ok:
                boleta.error_mensaje = str(resp)[:2000]
            boleta.save(update_fields=['track_id', 'estado', 'error_mensaje',
                                       'actualizada_at'])

        estilo = self.style.SUCCESS if ok else self.style.ERROR
        self.stdout.write(estilo(
            f"Envío {'OK' if ok else 'FALLÓ'} — trackId={track} estado={estado} "
            f"glosa={resp.get('glosa', '')} errores={resp.get('errores')}"))
