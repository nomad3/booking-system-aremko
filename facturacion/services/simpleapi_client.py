"""
Cliente HTTP para SimpleAPI (api.simpleapi.cl) — DTEs, sobres, envío y folios.

Contratos verificados en documentacion.simpleapi.cl (colección Postman, 2026-07-12):

1) Generar DTE/boleta:  POST api.simpleapi.cl/api/v1/dte/generar
   multipart: input = JSON {Documento{Encabezado{IdentificacionDTE, Emisor,
   Receptor, Totales}, Detalles[], Referencias[]}, Certificado{Rut, Password}}
   + files = certificado .pfx + files2 = CAF .xml.  Respuesta 200 = XML del DTE
   firmado y timbrado.  Emisor de BOLETA usa RazonSocialBoleta/GiroBoleta/
   DireccionOrigen/ComunaOrigen.  Líneas con precios BRUTOS (IVA incluido);
   Totales con MontoNeto/IVA/MontoTotal y MontoExento si hay líneas exentas.

2) Sobre de envío:  POST api.simpleapi.cl/api/v1/envio/generar
   input = {Certificado, Caratula{RutEmisor, RutReceptor: "60803000-K" (SII),
   FechaResolucion AAAA-MM-DD, NumeroResolucion}} + files = .pfx +
   files2..N = XMLs de los DTE.  Si son boletas → EnvioBoleta (máx 500).

3) Enviar al SII:  POST api.simpleapi.cl/api/v1/envio/enviar
   input = {Certificado, Ambiente: 0 cert / 1 prod, Tipo: 1 EnvioDTE / 2
   EnvioBoleta} + files = .pfx + files2 = sobre XML.
   Respuesta JSON: {trackId, estado, ok, glosa, errores, ...}.

4) Folios CAF:  POST servicios.simpleapi.cl/api/folios/get/{tipoDte}/{cantidad}
   input = {RutCertificado, Password, RutEmpresa, Ambiente: 0 cert / 1 prod}
   + files = .pfx.  Respuesta 200 = XML del CAF (<AUTORIZACION><CAF>...).
   Opera por scraping directo en el SII con el certificado (sin clave SII).

Rate limits: DTE 3/s y 40/min; Folios 1/s, 5/min, 100/h.

Secretos desde el entorno (Render): SIMPLEAPI_API_KEY, SII_CERT_B64 (.pfx en
base64), SII_CERT_PASSWORD.
"""
import base64
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://api.simpleapi.cl'
BASE_URL_SERVICIOS = 'https://servicios.simpleapi.cl'
PATH_GENERAR_DTE = '/api/v1/dte/generar'
PATH_GENERAR_SOBRE = '/api/v1/envio/generar'
PATH_ENVIAR_SII = '/api/v1/envio/enviar'
# Confirmado en el código fuente público del SDK oficial (chilesystems/SimpleSDK:
# Models/Estados/ConsultaTrackID.cs + Services/ApiBase.cs → api.simpleapi.cl/api/v1/).
PATH_CONSULTA_ENVIO = '/api/v1/consulta/envio'

# Tipos de envío al SII (enum TipoEnvio.EnvioType del SDK oficial).
TIPO_ENVIO_BOLETA = 2
# TIPO_ENVIO_RVD = 4 (Registro de Ventas Diarias) existe en el enum del SDK
# pero el SII YA NO LO ADMITE: desde 2021 el registro de ventas diarias lo
# construye el propio SII con las boletas que recibe. Enviarlo devuelve
# «Impuestos Internos ya no admite este tipo de documento».

RUT_SII = '60803000-K'
TIMEOUT = 90

TASA_IVA = 1.19


class SimpleAPIError(Exception):
    """Error de SimpleAPI con detalle del HTTP status y cuerpo."""


def obtener_api_key():
    return os.environ.get('SIMPLEAPI_API_KEY', '').strip()


def obtener_certificado():
    """Devuelve (cert_bytes, password) desde el entorno, o (None, None)."""
    b64 = os.environ.get('SII_CERT_B64', '').strip()
    password = os.environ.get('SII_CERT_PASSWORD', '')
    if not b64 or not password:
        return None, None
    try:
        return base64.b64decode(b64), password
    except Exception:
        logger.error("SII_CERT_B64 no es base64 válido")
        return None, None


def credenciales_listas():
    """True si hay API key + certificado + clave en el entorno."""
    cert, pwd = obtener_certificado()
    return bool(obtener_api_key() and cert and pwd)


def _post_multipart(url, input_json, archivos, como_json=False):
    """POST multipart con Authorization. `archivos` = lista de tuplas
    (nombre_campo, nombre_archivo, bytes, content_type)."""
    api_key = obtener_api_key()
    if not api_key:
        raise SimpleAPIError("Falta SIMPLEAPI_API_KEY en el entorno")

    files = {'input': (None, json.dumps(input_json), 'application/json')}
    for campo, nombre, contenido, ctype in archivos:
        files[campo] = (nombre, contenido, ctype)

    try:
        resp = requests.post(url, headers={'Authorization': api_key},
                             files=files, timeout=TIMEOUT)
    except requests.RequestException as exc:
        raise SimpleAPIError(f"Error de red hacia SimpleAPI: {exc}") from exc

    if resp.status_code != 200:
        raise SimpleAPIError(f"SimpleAPI HTTP {resp.status_code} en {url}: {resp.text[:600]}")

    if como_json:
        try:
            return resp.json()
        except ValueError as exc:
            raise SimpleAPIError(f"Respuesta no-JSON de {url}: {resp.text[:300]}") from exc
    return resp.text or ''


# ---------------------------------------------------------------------------
# Construcción del Documento (boleta 39/41)
# ---------------------------------------------------------------------------

def construir_documento_boleta(config, folio, fecha_emision, detalles,
                               cert_password, referencias=None, tipo_dte=39):
    """Arma el JSON `input` para POST /api/v1/dte/generar (boleta).

    `detalles`: lista de dicts {nombre, cantidad, precio (bruto, IVA incl.),
    exento (bool, opcional), unidad (str, opcional), descripcion (opcional)}.
    `referencias`: lista de dicts ya con las llaves SimpleAPI
    (TipoDocumento, FolioReferencia, FechaDocumentoReferencia, RazonReferencia).

    Totales: líneas brutas → neto = afecto/1.19 redondeado; IVA por diferencia;
    MontoExento solo si hay líneas exentas.
    """
    lineas = []
    total_afecto = 0
    total_exento = 0
    for det in detalles:
        cantidad = float(det.get('cantidad', 1))
        precio = float(det['precio'])
        monto_item = int(round(cantidad * precio))
        exento = bool(det.get('exento'))
        linea = {
            "IndicadorExento": 1 if exento else 0,
            "Nombre": str(det['nombre'])[:80],
            "Cantidad": cantidad,
            "Precio": precio,
            "Descuento": 0,
            "Recargo": 0,
            "MontoItem": monto_item,
        }
        if det.get('descripcion'):
            linea["Descripcion"] = str(det['descripcion'])[:1000]
        if det.get('unidad'):
            linea["UnidadMedida"] = str(det['unidad'])[:4]
        lineas.append(linea)
        if exento:
            total_exento += monto_item
        else:
            total_afecto += monto_item

    neto = int(round(total_afecto / TASA_IVA))
    iva = total_afecto - neto
    total = total_afecto + total_exento

    totales = {
        "MontoNeto": neto,
        "IVA": iva,
        "MontoTotal": total,
    }
    if total_exento:
        totales["MontoExento"] = total_exento

    documento = {
        "Documento": {
            "Encabezado": {
                "IdentificacionDTE": {
                    "TipoDTE": tipo_dte,
                    "Folio": folio,
                    "FechaEmision": fecha_emision.strftime('%Y-%m-%d'),
                    "IndicadorServicio": config.indicador_servicio,
                },
                "Emisor": {
                    "Rut": config.rut_emisor,
                    "RazonSocialBoleta": config.razon_social,
                    "GiroBoleta": config.giro_boleta,
                    "DireccionOrigen": config.direccion,
                    "ComunaOrigen": config.comuna,
                },
                "Receptor": {
                    "Rut": "66666666-6",
                    "RazonSocial": "Consumidor final",
                    "Direccion": "-",
                    "Comuna": "-",
                },
                "Totales": totales,
            },
            "Detalles": lineas,
        },
        "Certificado": {
            "Rut": config.rut_firmante,
            "Password": cert_password,
        },
    }
    if referencias:
        documento["Documento"]["Referencias"] = referencias
    return documento


# ---------------------------------------------------------------------------
# Operaciones contra SimpleAPI
# ---------------------------------------------------------------------------

def generar_boleta(documento_json, cert_bytes, caf_xml):
    """Genera y timbra una boleta. Devuelve el XML del DTE (str)."""
    xml = _post_multipart(
        BASE_URL + PATH_GENERAR_DTE,
        documento_json,
        [('files', 'certificado.pfx', cert_bytes, 'application/x-pkcs12'),
         ('files2', 'caf.xml', caf_xml.encode('ISO-8859-1', errors='replace'), 'text/xml')],
    )
    if '<DTE' not in xml:
        raise SimpleAPIError(f"Respuesta sin XML de DTE: {xml[:300]}")
    return xml


def generar_sobre(xmls_dte, cert_bytes, cert_password, config):
    """Genera el sobre EnvioBoleta con los XML de boletas. Devuelve XML del sobre."""
    caratula = {
        "RutEmisor": config.rut_emisor,
        "RutReceptor": RUT_SII,
        "FechaResolucion": config.fecha_resolucion.strftime('%Y-%m-%d')
                           if config.fecha_resolucion else '',
        "NumeroResolucion": config.numero_resolucion,
    }
    input_json = {
        "Certificado": {"Rut": config.rut_firmante, "Password": cert_password},
        "Caratula": caratula,
    }
    archivos = [('files', 'certificado.pfx', cert_bytes, 'application/x-pkcs12')]
    for i, xml in enumerate(xmls_dte, start=2):
        archivos.append((f'files{i}', f'dte_{i - 1}.xml',
                         xml.encode('ISO-8859-1', errors='replace'), 'text/xml'))
    sobre = _post_multipart(BASE_URL + PATH_GENERAR_SOBRE, input_json, archivos)
    if '<EnvioBOLETA' not in sobre and '<EnvioDTE' not in sobre:
        raise SimpleAPIError(f"Respuesta sin sobre de envío: {sobre[:300]}")
    return sobre


def enviar_sobre(sobre_xml, cert_bytes, cert_password, config, ambiente_num, tipo=2):
    """Envía el sobre al SII. tipo: 1=EnvioDTE, 2=EnvioBoleta, 4=RVD
    (consumo de folios). Devuelve dict con trackId/estado/ok según SimpleAPI."""
    input_json = {
        "Certificado": {"Rut": config.rut_firmante, "Password": cert_password},
        "Ambiente": ambiente_num,
        "Tipo": tipo,
    }
    return _post_multipart(
        BASE_URL + PATH_ENVIAR_SII,
        input_json,
        [('files', 'certificado.pfx', cert_bytes, 'application/x-pkcs12'),
         ('files2', 'sobre.xml', sobre_xml.encode('ISO-8859-1', errors='replace'), 'text/xml')],
        como_json=True,
    )


def consultar_estado_envio(track_id, cert_bytes, cert_password, config,
                           ambiente_num, servidor_boleta=True):
    """Consulta al SII (vía SimpleAPI) el estado de un envío por trackId.

    Endpoint tomado del código fuente público del SDK oficial
    (chilesystems/SimpleSDK, Models/Estados/ConsultaTrackID.cs):
    POST {base}/api/v1/consulta/envio — multipart con `input` JSON
    {RutEmpresa, TrackId, Ambiente, ServidorBoletaREST} + `file` (.pfx).
    Para boletas, ServidorBoletaREST=True (el SII de boletas es la API REST,
    no el SOAP de DTE estándar). Devuelve el JSON de SimpleAPI tal cual
    (estado REC/EPR/ACEPTADO/RECHAZADO según el SII).
    """
    # Mismo contrato multipart que enviar_sobre (el hermano que YA funciona):
    # input como dict (serializa _post_multipart), cert en el campo 'files'.
    input_json = {
        "RutEmpresa": config.rut_emisor,
        "TrackId": int(track_id),
        "Ambiente": ambiente_num,
        "ServidorBoletaREST": bool(servidor_boleta),
        "Certificado": {"Rut": config.rut_firmante, "Password": cert_password},
    }
    return _post_multipart(
        BASE_URL + PATH_CONSULTA_ENVIO,
        input_json,
        [('files', 'certificado.pfx', cert_bytes, 'application/x-pkcs12')],
        como_json=True,
    )


def solicitar_folios(tipo_dte, cantidad, cert_bytes, cert_password,
                     rut_firmante, rut_empresa, ambiente_num):
    """Solicita un CAF nuevo al SII (vía SimpleAPI Folios). Devuelve el XML CAF."""
    input_json = {
        "RutCertificado": rut_firmante,
        "Password": cert_password,
        "RutEmpresa": rut_empresa,
        "Ambiente": ambiente_num,
    }
    url = f"{BASE_URL_SERVICIOS}/api/folios/get/{tipo_dte}/{cantidad}"
    caf = _post_multipart(
        url, input_json,
        [('files', 'certificado.pfx', cert_bytes, 'application/x-pkcs12')],
    )
    if '<AUTORIZACION' not in caf and '<CAF' not in caf:
        raise SimpleAPIError(f"Respuesta sin CAF: {caf[:300]}")
    return caf
