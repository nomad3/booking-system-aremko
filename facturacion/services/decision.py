# -*- coding: utf-8 -*-
"""Quién todavía no decidió si emite boleta.

La pregunta «¿Desea generar la boleta electrónica?» nació en la tarjeta móvil
(02-09-2026). Pero se cobra por DOS caminos: la tarjeta y el formulario grande
del admin. En el admin no preguntaba nada, así que un cobro hecho ahí quedaba
sin boleta sin que nadie se enterara hasta revisar el listado — que es un
repaso posterior, no parte del cobro.

Este módulo tiene la única definición de «pago pendiente de decisión», para
que las dos pantallas no terminen respondiendo cosas distintas.
"""
import logging

logger = logging.getLogger(__name__)


def codigos_que_boletean():
    """Medios marcados para emitir boleta. Vacío ante cualquier problema:
    preguntar de más empuja a emitir un duplicado, que cuesta más de arreglar
    que una boleta que falta."""
    try:
        from facturacion.models import MedioPago
        return set(MedioPago.objects.filter(genera_boleta=True)
                   .values_list('codigo', flat=True))
    except Exception as exc:  # noqa: BLE001
        logger.warning('facturacion: no se pudieron leer los medios: %s', exc)
        return set()


def pagos_sin_resolver(venta):
    """Pagos de esta venta que debían boletear y nadie resolvió todavía.

    «Resuelto» es cualquiera de las dos: existe una boleta que no está en
    error, o alguien dejó constancia de que NO se emite. Un pago con boleta en
    error NO está resuelto: esa boleta no existe ante el SII.

    Las devoluciones (monto <= 0) quedan fuera: no se boletean, se anulan con
    nota de crédito — y esas se emiten en el sistema del SII.
    """
    if not venta or not getattr(venta, 'pk', None):
        return []
    codigos = codigos_que_boletean()
    if not codigos:
        return []
    try:
        from facturacion.models import BoletaElectronica, DecisionSinBoleta

        pagos = list(venta.pagos.filter(metodo_pago__in=codigos, monto__gt=0))
        if not pagos:
            return []
        ids = [p.pk for p in pagos]
        con_boleta = set(BoletaElectronica.objects
                         .filter(pago_id__in=ids)
                         .exclude(estado__in=('error', 'pendiente'))
                         .values_list('pago_id', flat=True))
        decididos = set(DecisionSinBoleta.objects
                        .filter(pago_id__in=ids).values_list('pago_id', flat=True))
        return [p for p in pagos
                if p.pk not in con_boleta and p.pk not in decididos]
    except Exception as exc:  # noqa: BLE001
        logger.warning('facturacion: no se pudo revisar la venta %s: %s',
                       getattr(venta, 'pk', None), exc)
        return []
