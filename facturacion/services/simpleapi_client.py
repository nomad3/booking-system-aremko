"""
Cliente HTTP para SimpleAPI (api.simpleapi.cl) — generación de DTEs.

Contrato verificado en documentacion.simpleapi.cl (colección Postman, 2026-07-11):
- Auth: header `Authorization: <ApiKey>` (la key se obtiene gratis en simpleapi.cl).
- POST /api/v1/dte/generar  → multipart/form-data:
    input  = JSON (Documento + Certificado{Rut, Password})
    files  = certificado digital .pfx
    files2 = archivo CAF .xml (rango de folios del SII)
  Respuesta 200 = XML del DTE firmado y timbrado (TED incluido).
- Rate limit API DTE: 3/seg, 40/min (sobra para ~200 boletas/mes).

Los endpoints de sobre de envío y envío al SII existen en la carpeta
"Envio de DTE" de la colección; sus paths exactos se fijan en la sesión de
certificación (constantes abajo, ajustables sin tocar el resto del código).

Secretos desde el entorno (Render):
- SIMPLEAPI_API_KEY   — API key de la cuenta SimpleAPI de Aremko.
- SII_CERT_B64        — certificado digital .pfx codificado en base64.
- SII_CERT_PASSWORD   — clave del certificado.
"""
import base64
import json
import logging
import os

import requests

logger = logging.getLogger(__name__)

BASE_URL = 'https://api.simpleapi.cl'
PATH_GENERAR_DTE = '/api/v1/dte/generar'
# Por confirmar en la sesión de certificación (carpeta "Envio de DTE" de la colección):
PATH_GENERAR_SOBRE = '/api/v1/envio/generar'
PATH_ENVIAR_SII = '/api/v1/envio/enviar'

TIMEOUT = 40


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


def construir_documento_boleta(config, folio, fecha_emision, monto_neto, monto_iva,
                               monto_total, glosa, cert_password, tipo_dte=39):
    """Arma el JSON `input` para POST /api/v1/dte/generar (boleta 39/41).

    Precios BRUTOS (IVA incluido), receptor consumidor final 66666666-6.
    """
    return {
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
                    "Direccion": config.direccion,
                    "Comuna": config.comuna,
                },
                "Receptor": {
                    "Rut": "66666666-6",
                    "RazonSocial": "Consumidor final",
                    "Direccion": "-",
                    "Comuna": "-",
                },
                "Totales": {
                    "MontoNeto": int(monto_neto),
                    "TasaIVA": 19,
                    "IVA": int(monto_iva),
                    "MontoTotal": int(monto_total),
                },
            },
            "Detalles": [{
                "IndicadorExento": 0,
                "Nombre": glosa[:80] or "Servicios Aremko",
                "Cantidad": 1.0,
                "Precio": int(monto_total),
                "MontoItem": int(monto_total),
            }],
        },
        "Certificado": {
            "Rut": config.rut_firmante,
            "Password": cert_password,
        },
    }


def generar_boleta(documento_json, cert_bytes, caf_xml):
    """POST /api/v1/dte/generar. Devuelve el XML del DTE firmado (str).

    Lanza SimpleAPIError con el detalle si la API responde error.
    """
    api_key = obtener_api_key()
    if not api_key:
        raise SimpleAPIError("Falta SIMPLEAPI_API_KEY en el entorno")

    files = {
        'input': (None, json.dumps(documento_json), 'application/json'),
        'files': ('certificado.pfx', cert_bytes, 'application/x-pkcs12'),
        'files2': ('caf.xml', caf_xml.encode('ISO-8859-1', errors='replace'), 'text/xml'),
    }
    try:
        resp = requests.post(
            BASE_URL + PATH_GENERAR_DTE,
            headers={'Authorization': api_key},
            files=files,
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        raise SimpleAPIError(f"Error de red hacia SimpleAPI: {exc}") from exc

    if resp.status_code != 200:
        raise SimpleAPIError(f"SimpleAPI HTTP {resp.status_code}: {resp.text[:500]}")

    xml = resp.text or ''
    if '<DTE' not in xml:
        raise SimpleAPIError(f"Respuesta sin XML de DTE: {xml[:300]}")
    return xml
