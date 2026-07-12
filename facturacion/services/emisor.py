"""
Servicio de emisión de boletas — idempotente y tolerante a fallas.

Regla de oro: emitir (o fallar emitiendo) JAMÁS debe romper el registro del
pago. Toda excepción queda capturada en la BoletaElectronica (estado 'error',
error_mensaje) para reintentar desde el admin.
"""
import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from facturacion.models import (BoletaElectronica, ConfiguracionFacturacion,
                                MedioPago, RangoFolios)
from facturacion.services import simpleapi_client

logger = logging.getLogger(__name__)

TASA_IVA = Decimal('1.19')


def calcular_montos(monto_total):
    """Desde el bruto (precios Aremko, IVA incluido): neto = total/1.19 redondeado."""
    total = int(monto_total)
    neto = int(round(total / float(TASA_IVA)))
    iva = total - neto
    return neto, iva


def medio_genera_boleta(codigo):
    medio = MedioPago.objects.filter(codigo=codigo).first()
    return bool(medio and medio.genera_boleta)


def glosa_para_pago(pago):
    vr = pago.venta_reserva
    partes = [f"Reserva #{vr.id}" if vr else "Venta Aremko"]
    try:
        # Savepoint: si esta consulta falla, NO puede dejar abortada la
        # transacción del caller (en Postgres un statement fallido aborta
        # toda la transacción aunque se capture la excepción).
        with transaction.atomic():
            primer_servicio = (vr.reservaservicios.select_related('servicio').first()
                               if vr else None)
            if primer_servicio and primer_servicio.servicio:
                partes.append(primer_servicio.servicio.nombre)
    except Exception:  # la glosa nunca debe botar la emisión
        pass
    partes.append("Aremko Spa")
    return " - ".join(partes)[:200]


def emitir_boleta_para_pago(pago, forzar_medio=False):
    """Emite (o reintenta) la boleta electrónica de un pago.

    Devuelve (boleta | None, mensaje). Idempotente: si ya existe una boleta
    definitiva para el pago, la devuelve sin crear otra (candado OneToOne).
    `forzar_medio=True` permite emitir aunque el medio esté marcado como
    no-boleteable (para casos excepcionales, solo desde el admin).
    """
    if pago.monto is None or int(pago.monto) <= 0:
        return None, "monto no positivo, no corresponde boleta"

    if not forzar_medio and not medio_genera_boleta(pago.metodo_pago):
        return None, f"el medio '{pago.metodo_pago}' no genera boleta (lo informa el recaudador o no es plata)"

    existente = BoletaElectronica.objects.filter(pago=pago).first()
    if existente and existente.estado not in ('error', 'pendiente'):
        return existente, f"ya existía (estado: {existente.get_estado_display()})"

    config = ConfiguracionFacturacion.get()
    neto, iva = calcular_montos(pago.monto)

    if existente:
        boleta = existente
    else:
        try:
            boleta = BoletaElectronica.objects.create(
                pago=pago,
                venta_reserva=pago.venta_reserva,
                ambiente=config.ambiente,
                monto_total=int(pago.monto),
                monto_neto=neto,
                monto_iva=iva,
                glosa=glosa_para_pago(pago),
            )
        except IntegrityError:
            # Carrera: otro proceso la creó entre el filter y el create.
            boleta = BoletaElectronica.objects.get(pago=pago)

    boleta.intentos += 1
    boleta.ambiente = config.ambiente

    if config.ambiente == 'simulado':
        boleta.estado = 'simulada'
        boleta.error_mensaje = ''
        boleta.emitida_at = timezone.now()
        boleta.save()
        return boleta, "boleta SIMULADA registrada (sin valor tributario)"

    # Ambientes reales: certificación o producción
    if not simpleapi_client.credenciales_listas():
        boleta.estado = 'error'
        boleta.error_mensaje = ("Faltan credenciales en el entorno: SIMPLEAPI_API_KEY / "
                                "SII_CERT_B64 / SII_CERT_PASSWORD")
        boleta.save()
        return boleta, boleta.error_mensaje

    if not config.rut_emisor or not config.rut_firmante:
        boleta.estado = 'error'
        boleta.error_mensaje = "Configura RUT emisor y RUT firmante en Configuración de facturación"
        boleta.save()
        return boleta, boleta.error_mensaje

    folio, rango = RangoFolios.asignar_folio(boleta.tipo_dte, config.ambiente)
    if folio is None:
        boleta.estado = 'error'
        boleta.error_mensaje = f"Sin folios CAF activos para DTE {boleta.tipo_dte} en {config.ambiente}"
        boleta.save()
        return boleta, boleta.error_mensaje

    cert_bytes, cert_password = simpleapi_client.obtener_certificado()
    documento = simpleapi_client.construir_documento_boleta(
        config=config,
        folio=folio,
        fecha_emision=timezone.localdate(),
        monto_neto=neto,
        monto_iva=iva,
        monto_total=int(pago.monto),
        glosa=boleta.glosa,
        cert_password=cert_password,
        tipo_dte=boleta.tipo_dte,
    )
    try:
        xml = simpleapi_client.generar_boleta(documento, cert_bytes, rango.caf_xml)
    except simpleapi_client.SimpleAPIError as exc:
        boleta.estado = 'error'
        boleta.error_mensaje = str(exc)[:2000]
        boleta.save()
        logger.warning("Emisión de boleta falló (pago %s): %s", pago.pk, exc)
        return boleta, f"error de emisión: {exc}"

    boleta.folio = folio
    boleta.xml_dte = xml
    boleta.estado = 'generada'
    boleta.error_mensaje = ''
    boleta.emitida_at = timezone.now()
    boleta.save()
    # El envío del sobre al SII (EnvioBOLETA) se conecta en la sesión de
    # certificación (paths en simpleapi_client). La boleta ya queda timbrada.
    return boleta, f"boleta generada y timbrada (folio {folio}, {config.ambiente})"
