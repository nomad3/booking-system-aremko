"""Empaquetar en la giftcard los extras que se vendieron junto con ella.

El caso que lo motivó (venta #6780, 07-09-2026): un cliente compra una Pausa
junto al Río como giftcard y le suma una ambientación romántica. Deborah hizo
lo natural desde la página de la venta: la giftcard por su precio fijo
($110.000) y la ambientación como servicio de la venta, fechado 02/02/2021
—una fecha de relleno, porque un servicio exige fecha—. Total $142.000,
correcto para quien paga. Pero la giftcard quedó en $110.000, la carta no
decía nada de la ambientación, y los $32.000 viven en una venta aparte con
fecha del 2021: al canjear, alguien tiene que acordarse.

No es un caso aislado: seis ventas con giftcard llevan servicios fechados en
2021 desde noviembre de 2025. Es la única forma que había de cobrar un extra
junto con una tarjeta.

Esto respeta ese hábito y cierra el círculo: los extras pasan A la giftcard.
Su monto sube en lo que valen, sus nombres quedan en «Incluye además» (que la
carta ya imprime), y las líneas de relleno se sacan de la venta. El total de
la venta no cambia; lo que cambia es que la tarjeta se explica sola y cubre lo
que promete.
"""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

# Antes de esta fecha no hubo reservas reales en el sistema: una línea fechada
# ahí es relleno para poder cobrar algo junto con una giftcard. El resto del
# código ya usa la misma frontera (ServiceHistory excluye < 2021-01-01).
FECHA_RELLENO_TOPE = datetime.date(2022, 1, 1)


def _precio_linea_servicio(r):
    pu = r.precio_unitario_venta
    if pu is None:
        pu = r.servicio.precio_base
    return Decimal(pu or 0) * Decimal(r.cantidad_personas or 0)


def _precio_linea_producto(p):
    pu = p.precio_unitario_venta
    if pu is None:
        pu = p.producto.precio_base
    return Decimal(pu or 0) * Decimal(p.cantidad or 0)


def extras_de(venta):
    """Los extras empaquetables de una venta, o lista vacía.

    Solo si la venta tiene giftcard. Cuentan: servicios con fecha de relleno
    (antes de 2022) y todos los productos —en una venta de giftcard, un
    espumante no es para quien paga sino para quien la recibe—. Los servicios
    con fecha real NO cuentan: esos son una reserva de verdad.

    Devuelve dicts {tipo, obj, nombre, monto} para que la confirmación muestre
    exactamente lo que va a pasar.
    """
    if not venta or not venta.pk or not venta.giftcards.exists():
        return []
    extras = []
    for r in venta.reservaservicios.select_related('servicio'):
        if r.fecha_agendamiento and r.fecha_agendamiento < FECHA_RELLENO_TOPE:
            extras.append({'tipo': 'servicio', 'obj': r,
                           'nombre': r.servicio.nombre,
                           'monto': _precio_linea_servicio(r)})
    for p in venta.reservaproductos.select_related('producto'):
        nombre = p.producto.nombre
        if (p.cantidad or 1) > 1:
            nombre = f'{p.cantidad}× {nombre}'
        extras.append({'tipo': 'producto', 'obj': p, 'nombre': nombre,
                       'monto': _precio_linea_producto(p)})
    return extras


def giftcard_destino(venta):
    """La giftcard que recibe los extras. Si hay varias, la más nueva."""
    return venta.giftcards.order_by('-id').first()


def empaquetar(venta, giftcard, usuario=None):
    """Mueve los extras de la venta a la giftcard. Devuelve un resumen.

    Una sola transacción: o pasa todo o no pasa nada. Deja rastro en tres
    lugares —el Historial de la giftcard, los comentarios de la venta y el
    log— porque toca el monto de una tarjeta, que es plata.
    """
    extras = extras_de(venta)
    if not extras:
        return {'ok': False, 'motivo': 'No hay extras que empaquetar.'}
    if giftcard is None or giftcard.venta_reserva_id != venta.pk:
        return {'ok': False, 'motivo': 'La giftcard no pertenece a esta venta.'}

    total_extras = sum((e['monto'] for e in extras), Decimal(0))
    nombres = [e['nombre'] for e in extras]
    antes_ini, antes_disp = giftcard.monto_inicial, giftcard.monto_disponible

    with transaction.atomic():
        giftcard.monto_inicial = (giftcard.monto_inicial or 0) + total_extras
        giftcard.monto_disponible = (giftcard.monto_disponible or 0) + total_extras
        if giftcard.estado == 'cobrado' and giftcard.monto_disponible > 0:
            giftcard.estado = 'por_cobrar'
        previo = (giftcard.detalle_especial or '').strip()
        nuevo = ', '.join(nombres)
        giftcard.detalle_especial = f'{previo}, {nuevo}' if previo else nuevo
        giftcard.save()

        for e in extras:
            e['obj'].delete()

        venta.calcular_total()
        venta.save(update_fields=['total'])

        quien = getattr(usuario, 'username', None) or 'sistema'
        # Los miles se formatean aparte: un replace(',', '.') sobre la frase
        # entera también pisaba la coma de la lista ("R1, 1 Espumante" quedaba
        # "R1. 1 Espumante"). Se vio en el primer uso real, venta #6780.
        def _clp(n):
            return '$' + f'{int(n or 0):,}'.replace(',', '.')
        detalle = (f'Empaquetado en la giftcard {giftcard.codigo}: {nuevo}. '
                   f'La tarjeta pasó de {_clp(antes_ini)} a '
                   f'{_clp(giftcard.monto_inicial)}.')
        stamp = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
        venta.comentarios = ((venta.comentarios or '').rstrip() +
                             f'\n[{stamp} · {quien}] {detalle}').strip()
        venta.save(update_fields=['comentarios'])

        try:
            from django.contrib.admin.models import CHANGE, LogEntry
            from django.contrib.contenttypes.models import ContentType

            if getattr(usuario, 'pk', None):
                LogEntry.objects.log_action(
                    user_id=usuario.pk,
                    content_type_id=ContentType.objects.get_for_model(giftcard).pk,
                    object_id=giftcard.pk, object_repr=str(giftcard),
                    action_flag=CHANGE, change_message=detalle)
        except Exception:  # noqa: BLE001 — el rastro del admin no puede voltear la operación
            logger.exception('[giftcard] no se pudo escribir el LogEntry del empaquetado')

    logger.warning('[giftcard] %s empaquetó en %s: %s (disp %s→%s)', quien,
                   giftcard.codigo, nuevo, antes_disp, giftcard.monto_disponible)
    return {'ok': True, 'nombres': nombres, 'total_extras': total_extras,
            'monto_antes': antes_ini, 'monto_despues': giftcard.monto_inicial,
            'codigo': giftcard.codigo}
