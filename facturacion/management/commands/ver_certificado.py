"""Muestra de QUIÉN es el certificado con el que firmamos (P-16).

El SII rechazó el envío con «Rut No Autorizado a Firmar». Eso puede ser dos
cosas muy distintas: (a) el RUT que declaramos no es el del certificado —
culpa nuestra, se arregla en la configuración; (b) el RUT es correcto pero el
SII no lo tiene autorizado para firmar por la empresa — trámite de Jorge.

Esto imprime el titular y la vigencia del certificado y los compara con la
configuración. Nunca imprime la clave ni el contenido del certificado.
"""
from django.core.management.base import BaseCommand, CommandError

from facturacion.models import ConfiguracionFacturacion
from facturacion.services import simpleapi_client


def _solo_digitos(rut):
    """Normaliza un RUT para compararlo: sin puntos, sin guión y SIN ceros de
    relleno. El certificado trae 07604892-4 y la configuración 7604892-4: es
    el mismo RUT, y compararlos literalmente hacía gritar «no coincide»."""
    limpio = ''.join(c for c in (rut or '') if c.isalnum()).upper()
    return limpio.lstrip('0')


class Command(BaseCommand):
    help = 'Titular y vigencia del certificado digital, contra la configuración.'

    def handle(self, *args, **opts):
        from cryptography.hazmat.primitives.serialization import pkcs12

        cert_bytes, password = simpleapi_client.obtener_certificado()
        if not cert_bytes:
            raise CommandError('No hay certificado en el entorno.')
        _, cert, _ = pkcs12.load_key_and_certificates(
            cert_bytes, password.encode())
        if cert is None:
            raise CommandError('El .pfx no trae certificado.')

        titular = {}
        for attr in cert.subject:
            titular[attr.oid._name or attr.oid.dotted_string] = str(attr.value)

        config = ConfiguracionFacturacion.get()
        self.stdout.write('--- CERTIFICADO ---')
        for k, v in titular.items():
            self.stdout.write(f'  {k}: {v}')
        emisor_cert = ', '.join(str(a.value) for a in cert.issuer
                                if (a.oid._name or '') == 'commonName')
        self.stdout.write(f'  emitido por: {emisor_cert}')
        self.stdout.write(f'  vigente: {cert.not_valid_before_utc:%d-%m-%Y} '
                          f'→ {cert.not_valid_after_utc:%d-%m-%Y}')

        # Los certificados chilenos (e-certchile) no ponen el RUT en el
        # subject sino en la extensión subjectAltName, como otherName.
        rut_cert = titular.get('serialNumber', '')
        if not rut_cert:
            try:
                from cryptography.x509.oid import ExtensionOID
                san = cert.extensions.get_extension_for_oid(
                    ExtensionOID.SUBJECT_ALTERNATIVE_NAME).value
                for nombre in san:
                    crudo = getattr(nombre, 'value', b'')
                    if isinstance(crudo, bytes):
                        texto = ''.join(chr(c) for c in crudo
                                        if 45 <= c <= 57 or c in (75, 107))
                        if len(texto) >= 8 and any(c.isdigit() for c in texto):
                            rut_cert = texto.strip('-')
                            break
            except Exception as exc:
                self.stdout.write(f'  (no se pudo leer el RUT del certificado: {exc})')
        self.stdout.write('--- CONFIGURACIÓN ---')
        self.stdout.write(f'  rut_firmante (va como RutEnvia): {config.rut_firmante}')
        self.stdout.write(f'  rut_emisor  (la empresa):        {config.rut_emisor}')

        if rut_cert:
            coincide = _solo_digitos(rut_cert) == _solo_digitos(config.rut_firmante)
            self.stdout.write(
                f'--- VEREDICTO: el RUT del certificado ({rut_cert}) '
                f'{"COINCIDE" if coincide else "NO COINCIDE"} con rut_firmante ---')
            if coincide:
                self.stdout.write('  Entonces el XML declara bien quién firma: '
                                  'lo que falta es la autorización en el SII.')
            else:
                self.stdout.write('  Es nuestro: hay que corregir rut_firmante.')
