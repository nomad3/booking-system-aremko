"""Inspección forense del set de pruebas (P-16) tras el rechazo de schema.

El SII rechazó el sobre con LSX-00204 «extra data at end of complex element»
(2026-08-31, trackId 32032105). Este comando muestra los BYTES reales donde
ese error puede vivir: cabeza y cola de cada DTE guardado (en repr, para ver
BOM/espacios/saltos invisibles), las COSTURAS del sobre entre un </DTE> y el
siguiente <DTE, y la cola del sobre. No envía nada al SII: solo regenera el
sobre vía SimpleAPI y lo imprime.
"""
import re

from django.core.management.base import BaseCommand, CommandError

from facturacion.models import BoletaElectronica, ConfiguracionFacturacion
from facturacion.services import simpleapi_client


class Command(BaseCommand):
    help = 'Imprime cabezas/colas de los DTE del set y las costuras del sobre.'

    def handle(self, *args, **opts):
        boletas = list(BoletaElectronica.objects
                       .filter(caso_set__startswith='CASO')
                       .order_by('folio'))
        if not boletas:
            raise CommandError('No hay boletas del set.')

        for b in boletas:
            x = b.xml_dte or ''
            self.stdout.write(f'--- {b.caso_set} folio={b.folio} len={len(x)}')
            self.stdout.write(f'    HEAD: {x[:90]!r}')
            self.stdout.write(f'    TAIL: {x[-120:]!r}')

        config = ConfiguracionFacturacion.get()
        if not simpleapi_client.credenciales_listas():
            raise CommandError('Faltan credenciales.')
        cert_bytes, cert_password = simpleapi_client.obtener_certificado()
        sobre = simpleapi_client.generar_sobre([b.xml_dte for b in boletas],
                                               cert_bytes, cert_password, config)
        self.stdout.write(f'=== SOBRE len={len(sobre)}')
        # Las costuras: qué hay exactamente entre un DTE y el siguiente.
        for m in re.finditer(r'</DTE>(.{0,120}?)<DTE', sobre, re.DOTALL):
            self.stdout.write(f'    COSTURA: {m.group(1)!r}')
        self.stdout.write(f'    TAIL DEL SOBRE: {sobre[-400:]!r}')
        # ¿Prólogos XML interiores? (solo debe haber UNO, al inicio)
        self.stdout.write(f'    prólogos <?xml: {sobre.count("<?xml")}')
