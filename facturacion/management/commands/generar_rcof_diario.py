"""
Genera y valida el RCOF (Reporte de Consumo de Folios) del día — punto 4 de
la Declaración de Cumplimiento del SII («Envío diario del Reporte de
Consumo de Folios»).

El SII eliminó la OBLIGACIÓN de enviarlo en agosto de 2022, y su API lo
rechaza de plano si se intenta transmitir: "Impuestos Internos ya no admite
este tipo de documento" (verificado con el comando `enviar_rcof` durante la
certificación — no es un bug nuestro, es una decisión del SII). Por eso este
comando NO envía nada: genera, firma y valida el XML contra el esquema
oficial, y guarda el resultado como evidencia de que el sistema SIGUE siendo
capaz de producirlo — todos los días, listo para presentar si el SII lo
pidiera. Eso es lo que la declaración pregunta en la práctica: capacidad, no
un envío que el propio SII bloquea.

Corre para AYER por defecto: el consumo de folios de un día solo está
completo una vez que el día terminó.

Idempotente: si ya existe un reporte válido para esa fecha/ambiente/secuencia,
no lo regenera (usa --forzar).

Uso:
  python manage.py generar_rcof_diario                        # ayer, ambiente activo
  python manage.py generar_rcof_diario --fecha 2026-09-02
  python manage.py generar_rcof_diario --ambiente certificacion --forzar
"""
import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from facturacion.models import (BoletaElectronica, ConfiguracionFacturacion,
                                ReporteConsumoFolios)
from facturacion.services import rcof_builder, simpleapi_client

XSD = Path('/app/docs/certificacion_sii/ConsumoFolio_v10.xsd')


class Command(BaseCommand):
    help = ('Genera y valida (sin enviar — el SII rechaza este documento por '
            'API) el RCOF del día: evidencia de capacidad para la declaración.')

    def add_arguments(self, parser):
        parser.add_argument('--fecha', type=str, default='')
        parser.add_argument('--secuencia', type=int, default=1)
        parser.add_argument('--ambiente', type=str, default='')
        parser.add_argument('--forzar', action='store_true',
                            help='Regenerar aunque ya exista un reporte válido para esa fecha.')

    def handle(self, *args, **opts):
        config = ConfiguracionFacturacion.get()
        ambiente = opts['ambiente'] or config.ambiente
        fecha = (datetime.date.fromisoformat(opts['fecha']) if opts['fecha']
                 else timezone.localdate() - datetime.timedelta(days=1))

        if ambiente not in ('certificacion', 'produccion'):
            self.stdout.write(f"Ambiente '{ambiente}' no genera RCOF real. Nada que hacer.")
            return

        existente = ReporteConsumoFolios.objects.filter(
            ambiente=ambiente, fecha=fecha, secuencia=opts['secuencia']).first()
        if existente and existente.valido and not opts['forzar']:
            self.stdout.write(f"Ya existe un RCOF válido para {fecha} ({ambiente}) — se reutiliza.")
            return

        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()

        boletas = [
            b for b in BoletaElectronica.objects.filter(ambiente=ambiente)
                      .exclude(estado='error').order_by('folio')
            if b.xml_dte and f'<FchEmis>{fecha:%Y-%m-%d}</FchEmis>' in b.xml_dte
        ]
        if not boletas:
            # Día sin boletas es un resultado válido (0 folios), no una
            # falla -- un día de cierre no debería sonar como alarma.
            self.stdout.write(f"Sin boletas del {fecha} en {ambiente}: nada que reportar.")
            return

        sin_firma, doc_id = rcof_builder.construir_consumo_folios(
            config, fecha, boletas, secuencia=opts['secuencia'],
            timestamp=timezone.localtime())
        xml = rcof_builder.firmar(sin_firma, doc_id, cert_bytes, cert_password)
        valido, error_validacion = self._validar_contra_xsd(xml)

        ReporteConsumoFolios.objects.update_or_create(
            ambiente=ambiente, fecha=fecha, secuencia=opts['secuencia'],
            defaults={
                'cantidad_folios': len(boletas),
                'monto_total': sum(int(b.monto_total or 0) for b in boletas),
                'xml': xml, 'valido': valido, 'error_validacion': error_validacion,
            })

        if not valido:
            raise CommandError(f'RCOF del {fecha} generado pero NO válido: {error_validacion}')
        self.stdout.write(self.style.SUCCESS(
            f'RCOF del {fecha} ({ambiente}): {len(boletas)} folio(s), válido.'))

    def _validar_contra_xsd(self, xml):
        """(válido, error) — aparte para que los tests la reemplacen sin
        necesitar un certificado real ni depender del archivo XSD en disco."""
        if not XSD.exists():
            return False, f'Falta el XSD en {XSD}'
        from lxml import etree
        schema = etree.XMLSchema(etree.parse(str(XSD)))
        arbol = etree.fromstring(xml.encode('ISO-8859-1', errors='replace'))
        if not schema.validate(arbol):
            return False, '\n'.join(f'línea {e.line}: {e.message}' for e in schema.error_log)
        return True, ''
