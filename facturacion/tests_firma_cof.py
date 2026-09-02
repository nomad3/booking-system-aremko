"""La firma del consumo de folios pasa DOS compuertas antes de salir.

Historia (02-09-2026): la primera versión la escribí a mano —canonicalizar,
huella, firmar el SignedInfo— y el SII la rechazó con «Error en Firma». Un
verificador estándar también la rechazaba: el problema no era el SII. Ahora
firma `signxml`, y su salida por defecto tampoco servía: el esquema del SII es
MÁS estricto que el XML-DSig genérico y lo dijo al validar —una sola Transform,
y KeyValue antes del X509Data—.

Las dos comprobaciones tienen que correr juntas: una firma criptográficamente
válida con la forma equivocada la rechaza el esquema, y una con la forma
correcta mal firmada la rechaza el SII. Cada una sola da falsa tranquilidad.

Ejecutar:
    python manage.py test facturacion.tests_firma_cof
"""
from __future__ import annotations

import datetime

from django.test import TestCase


def _certificado_de_juguete():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    suj = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'PRUEBA')])
    cert = (x509.CertificateBuilder().subject_name(suj).issuer_name(suj)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(datetime.datetime.utcnow() - datetime.timedelta(days=1))
            .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=30))
            .sign(key, hashes.SHA256()))
    pfx = pkcs12.serialize_key_and_certificates(
        b'p', key, cert, None, serialization.BestAvailableEncryption(b'clave'))
    return pfx, cert


class _Config:
    rut_emisor = '76485192-7'
    rut_firmante = '7604892-4'
    fecha_resolucion = datetime.date(2026, 7, 12)
    numero_resolucion = 0


class _Boleta:
    def __init__(self, folio, neto, iva, total):
        self.folio, self.monto_neto, self.monto_iva, self.monto_total = (
            folio, neto, iva, total)


class LaFirmaDelConsumoDeFolios(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from facturacion.services import rcof_builder

        cls.pfx, cls.cert = _certificado_de_juguete()
        sin_firma, doc_id = rcof_builder.construir_consumo_folios(
            _Config(), datetime.date(2026, 9, 2),
            [_Boleta(29, 25042, 4758, 29800), _Boleta(30, 1714, 326, 2040)])
        cls.xml = rcof_builder.firmar(sin_firma, doc_id, cls.pfx, 'clave')

    def test_un_verificador_estandar_la_da_por_valida(self):
        from lxml import etree
        from signxml import (DigestAlgorithm, SignatureConfiguration,
                             SignatureMethod, XMLVerifier)

        cfg = SignatureConfiguration(
            signature_methods=frozenset([SignatureMethod.RSA_SHA1]),
            digest_algorithms=frozenset([DigestAlgorithm.SHA1]))
        XMLVerifier().verify(etree.fromstring(self.xml.encode('ISO-8859-1')),
                             x509_cert=self.cert, expect_config=cfg)

    def test_el_esquema_del_sii_la_acepta(self):
        import os

        from django.conf import settings
        from lxml import etree

        xsd = os.path.join(settings.BASE_DIR, 'docs', 'certificacion_sii',
                           'ConsumoFolio_v10.xsd')
        schema = etree.XMLSchema(etree.parse(xsd))
        doc = etree.fromstring(self.xml.encode('ISO-8859-1'))
        self.assertTrue(schema.validate(doc),
                        '; '.join(e.message for e in schema.error_log)[:400])

    def test_una_sola_transform(self):
        # El esquema del SII admite solo la de enveloped-signature; la librería
        # agrega una segunda de canonicalización si no se le dice que no.
        self.assertEqual(self.xml.count('<ds:Transform '), 1)

    def test_el_keyvalue_va_antes_del_x509(self):
        # Al revés, el esquema del SII la rechaza: «X509Data no esperado,
        # se esperaba KeyValue».
        self.assertLess(self.xml.index('KeyValue'), self.xml.index('X509Data'))

    def test_firma_con_SHA1_porque_es_lo_que_el_sii_especifica(self):
        self.assertIn('rsa-sha1', self.xml)
