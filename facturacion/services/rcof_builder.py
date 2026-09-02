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
    """Firma XML-DSig como la pide el SII: referencia al documento, SHA1,
    RSA-SHA1, canonicalización inclusiva y el certificado en el KeyInfo."""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.serialization import pkcs12
    from lxml import etree

    llave, cert, _ = pkcs12.load_key_and_certificates(
        cert_bytes, cert_password.encode())
    if llave is None or cert is None:
        raise ValueError('El .pfx no trae llave o certificado.')

    nums = llave.public_key().public_numbers()
    b64 = lambda x: base64.b64encode(x).decode()
    modulo = b64(nums.n.to_bytes((nums.n.bit_length() + 7) // 8, 'big'))
    exponente = b64(nums.e.to_bytes((nums.e.bit_length() + 7) // 8, 'big'))
    x509 = b64(cert.public_bytes(serialization.Encoding.DER))

    # Andamio de la firma: se rellena con los valores reales más abajo.
    firma = (
        f'<Signature xmlns="{NS_DS}"><SignedInfo>'
        '<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        f'<SignatureMethod Algorithm="{NS_DS}rsa-sha1"/>'
        f'<Reference URI="#{doc_id}"><Transforms>'
        f'<Transform Algorithm="{NS_DS}enveloped-signature"/></Transforms>'
        f'<DigestMethod Algorithm="{NS_DS}sha1"/><DigestValue></DigestValue>'
        '</Reference></SignedInfo><SignatureValue></SignatureValue>'
        '<KeyInfo><KeyValue><RSAKeyValue>'
        f'<Modulus>{modulo}</Modulus><Exponent>{exponente}</Exponent>'
        '</RSAKeyValue></KeyValue>'
        f'<X509Data><X509Certificate>{x509}</X509Certificate></X509Data>'
        '</KeyInfo></Signature>'
    )
    completo = xml_sin_firma.replace('</ConsumoFolios>', firma + '</ConsumoFolios>')
    arbol = etree.fromstring(completo.encode('ISO-8859-1', errors='replace'))

    # 1) Huella del documento referenciado, sobre su forma canónica.
    doc = arbol.find(f'{{{NS_SII}}}DocumentoConsumoFolios')
    canon_doc = etree.tostring(doc, method='c14n', exclusive=False, with_comments=False)
    digest = base64.b64encode(hashlib.sha1(canon_doc).digest()).decode()
    arbol.find(f'.//{{{NS_DS}}}DigestValue').text = digest

    # 2) La firma va sobre el SignedInfo YA con la huella dentro.
    signed_info = arbol.find(f'.//{{{NS_DS}}}SignedInfo')
    canon_si = etree.tostring(signed_info, method='c14n', exclusive=False,
                              with_comments=False)
    valor = llave.sign(canon_si, padding.PKCS1v15(), hashes.SHA1())
    arbol.find(f'.//{{{NS_DS}}}SignatureValue').text = base64.b64encode(valor).decode()

    cuerpo = etree.tostring(arbol, encoding='ISO-8859-1').decode('ISO-8859-1')
    if cuerpo.startswith('<?xml'):
        cuerpo = cuerpo.split('?>', 1)[1].lstrip()
    return '<?xml version="1.0" encoding="ISO-8859-1"?>\n' + cuerpo
