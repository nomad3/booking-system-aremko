"""Arma y FIRMA el Registro de Ventas Diarias (ex-RCOF) del SII.

SimpleAPI no lo genera: su catálogo público tiene 22 rutas y ninguna es de
consumo de folios (comprobado el 31-08-2026 sondeando rutas: las reales
responden 401 y las inventadas 404). Lo que sí acepta es ENVIARLO, con
`Tipo=4` en /api/v1/Envio/enviar. Así que el XML lo construimos y lo firmamos
nosotros, contra ConsumoFolio_v10.xsd.

Y no es solo para certificar: desde que se declara cumplimiento ante el SII,
el consumo de folios es una obligación DIARIA.
"""
import base64
import hashlib
from xml.sax.saxutils import escape

NS_SII = 'http://www.sii.cl/SiiDte'
NS_DS = 'http://www.w3.org/2000/09/xmldsig#'
TASA_IVA_PCT = 19


def _rangos(folios):
    """Agrupa folios sueltos en tramos consecutivos: [14,15,16,18] → [(14,16),(18,18)]."""
    tramos = []
    for f in sorted(folios):
        if tramos and f == tramos[-1][1] + 1:
            tramos[-1][1] = f
        else:
            tramos.append([f, f])
    return [(a, b) for a, b in tramos]


def construir_consumo_folios(config, fecha, boletas, secuencia=1, timestamp=None):
    """XML sin firmar del consumo de folios de un día, para las boletas dadas."""
    folios = [b.folio for b in boletas]
    neto = sum(int(b.monto_neto or 0) for b in boletas)
    iva = sum(int(b.monto_iva or 0) for b in boletas)
    total = sum(int(b.monto_total or 0) for b in boletas)
    exento = max(0, total - neto - iva)
    dia = fecha.strftime('%Y-%m-%d')
    firma_ts = (timestamp or fecha).strftime('%Y-%m-%dT%H:%M:%S')

    partes = [
        f'<Caratula version="1.0">',
        f'<RutEmisor>{escape(config.rut_emisor)}</RutEmisor>',
        f'<RutEnvia>{escape(config.rut_firmante)}</RutEnvia>',
        f'<FchResol>{config.fecha_resolucion:%Y-%m-%d}</FchResol>',
        f'<NroResol>{int(config.numero_resolucion or 0)}</NroResol>',
        f'<FchInicio>{dia}</FchInicio>',
        f'<FchFinal>{dia}</FchFinal>',
        f'<SecEnvio>{int(secuencia)}</SecEnvio>',
        f'<TmstFirmaEnv>{firma_ts}</TmstFirmaEnv>',
        '</Caratula>',
        '<Resumen>',
        '<TipoDocumento>39</TipoDocumento>',
        f'<MntNeto>{neto}</MntNeto>',
        f'<MntIva>{iva}</MntIva>',
        f'<TasaIVA>{TASA_IVA_PCT}</TasaIVA>',
        f'<MntExento>{exento}</MntExento>',
        f'<MntTotal>{total}</MntTotal>',
        f'<FoliosEmitidos>{len(folios)}</FoliosEmitidos>',
        '<FoliosAnulados>0</FoliosAnulados>',
        f'<FoliosUtilizados>{len(folios)}</FoliosUtilizados>',
    ]
    for ini, fin in _rangos(folios):
        partes.append(f'<RangoUtilizados><Inicial>{ini}</Inicial>'
                      f'<Final>{fin}</Final></RangoUtilizados>')
    partes.append('</Resumen>')

    doc_id = f'CF_{fecha:%Y%m%d}_{int(secuencia)}'
    return (
        '<?xml version="1.0" encoding="ISO-8859-1"?>\n'
        f'<ConsumoFolios xmlns="{NS_SII}" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:schemaLocation="{NS_SII} ConsumoFolio_v10.xsd" version="1.0">'
        f'<DocumentoConsumoFolios ID="{doc_id}">'
        + ''.join(partes) +
        '</DocumentoConsumoFolios>'
        '</ConsumoFolios>'
    ), doc_id


def firmar(xml_sin_firma, doc_id, cert_bytes, cert_password):
    """Firma el consumo de folios con XML-DSig, como lo pide el SII.

    Usa `signxml` y NO una implementación a mano. La primera versión la escribí
    a pulso —canonicalizar, calcular la huella, firmar el SignedInfo— y el SII
    la rechazó con «Error en Firma» (02-09-2026). Un verificador estándar
    también la rechazaba, mientras que la de la librería se verifica sola: el
    problema no era el SII sino la firma. XML-DSig tiene demasiadas sutilezas
    de canonicalización y espacios de nombres como para escribirlo uno mismo.

    SHA-1 no es una elección: es lo que especifica el SII para DTE. Por eso hay
    que desactivar la guarda de la librería, que lo bloquea por inseguro.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.serialization import pkcs12
    from lxml import etree
    from signxml import (CanonicalizationMethod, DigestAlgorithm,
                         SignatureConstructionMethod, SignatureMethod, XMLSigner)

    llave, cert, _ = pkcs12.load_key_and_certificates(
        cert_bytes, cert_password.encode())
    if llave is None or cert is None:
        raise ValueError('El .pfx no trae llave o certificado.')

    class _FirmadorSII(XMLSigner):
        def check_deprecated_methods(self):
            return None  # el SII firma con SHA-1

    firmador = _FirmadorSII(
        method=SignatureConstructionMethod.enveloped,
        signature_algorithm=SignatureMethod.RSA_SHA1,
        digest_algorithm=DigestAlgorithm.SHA1,
        c14n_algorithm=CanonicalizationMethod.CANONICAL_XML_1_0)

    arbol = etree.fromstring(xml_sin_firma.encode('ISO-8859-1', errors='replace'))
    firmado = firmador.sign(
        arbol,
        key=llave.private_bytes(serialization.Encoding.PEM,
                                serialization.PrivateFormat.PKCS8,
                                serialization.NoEncryption()),
        cert=cert.public_bytes(serialization.Encoding.PEM),
        reference_uri=f'#{doc_id}',
        # Dos exigencias del esquema del SII, más estrictas que el XML-DSig
        # genérico (las dijo su propio XSD al validar): una sola Transform —la
        # de enveloped-signature—, y KeyInfo con KeyValue ANTES del X509Data.
        exclude_c14n_transform_element=True,
        always_add_key_value=True)

    cuerpo = etree.tostring(firmado, encoding='ISO-8859-1').decode('ISO-8859-1')
    if cuerpo.startswith('<?xml'):
        cuerpo = cuerpo.split('?>', 1)[1].lstrip()
    return '<?xml version="1.0" encoding="ISO-8859-1"?>\n' + cuerpo
