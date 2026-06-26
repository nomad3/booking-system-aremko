"""Ficha de Reserva del cliente (Reserva-cliente-digital) — Fase 1, solo lectura.

Página móvil con link tokenizado que el cliente abre para ver su reserva:
- Cabecera con N° de reserva + estado de pago (Pendiente / Parcialmente pagada / Pagada).
- Botón 1: Servicios contratados (lista viva, solo lectura).
- Botón 2: Tips (reusa el texto compacto de tips_reserva_view).
- Botón 3: Comanda digital → abre el sistema de comanda que YA existe. Se bloquea
  cuando el recepcionista pone la reserva en estado 'checkout'.

El token es FIRMADO (django.core.signing), no adivinable y sin migración: deriva del
SECRET_KEY, así nadie ve la reserva de otro cambiando el id en la URL.
"""

import logging

from django.core import signing
from django.http import Http404
from django.shortcuts import render, redirect

from ..models import VentaReserva, ConfiguracionTips
from .tips_reserva_view import _generar_texto_tips

logger = logging.getLogger(__name__)

FICHA_SALT = 'ficha-reserva-cliente-v1'

def _clp(n):
    """Formatea un monto CLP con puntos de miles y signo: 210000 -> '$210.000', -30000 -> '−$30.000'."""
    n = int(n or 0)
    s = f"{abs(n):,}".replace(',', '.')
    return f"−${s}" if n < 0 else f"${s}"


ESTADO_PAGO_FICHA = {
    'pendiente': ('Pendiente de pago', 'pen'),
    'parcial':   ('Parcialmente pagada', 'par'),
    'pagado':    ('Pagada', 'pag'),
    'cancelado': ('Cancelada', 'can'),
}


def token_para_reserva(venta_id):
    """Token firmado (no adivinable) para la ficha de una reserva."""
    return signing.dumps(int(venta_id), salt=FICHA_SALT)


def url_ficha_reserva(venta_id):
    """URL pública completa de la ficha (para el admin / cajón)."""
    from django.urls import reverse
    from django.conf import settings
    base = getattr(settings, 'COMANDA_PUBLIC_BASE_URL', 'https://www.aremko.cl')
    return f"{base}{reverse('ventas:ficha_reserva_cliente', kwargs={'token': token_para_reserva(venta_id)})}"


def _venta_desde_token(token):
    """VentaReserva desde el token firmado, o Http404 si el token es inválido."""
    try:
        venta_id = signing.loads(token, salt=FICHA_SALT)
    except signing.BadSignature:
        raise Http404('Link inválido')
    venta = (VentaReserva.objects
             .select_related('cliente')
             .filter(id=venta_id)
             .first())
    if venta is None:
        raise Http404('Reserva no encontrada')
    return venta


def _lineas_servicios(venta):
    """Servicios + productos de la reserva como líneas para mostrar (solo lectura)."""
    lineas = []
    for rs in venta.reservaservicios.select_related('servicio').all():
        precio = rs.precio_unitario_venta if rs.precio_unitario_venta is not None else (rs.servicio.precio_base or 0)
        cant = rs.cantidad_personas or 1
        subtotal = int(precio) * cant
        nombre = rs.servicio.nombre
        lineas.append({
            'nombre': nombre,
            'fecha': rs.fecha_agendamiento,
            'hora': rs.hora_inicio,
            'monto_str': _clp(subtotal),
            'es_descuento': subtotal < 0 or 'descuento' in (nombre or '').lower(),
        })
    for rp in venta.reservaproductos.select_related('producto').all():
        precio = rp.precio_unitario_venta if rp.precio_unitario_venta is not None else (rp.producto.precio_base or 0)
        cant = rp.cantidad or 1
        lineas.append({
            'nombre': rp.producto.nombre,
            'fecha': None,
            'hora': None,
            'monto_str': _clp(int(precio) * cant),
            'es_descuento': False,
            'es_producto': True,
            'cantidad': cant,
        })
    return lineas


def ficha_reserva_cliente(request, token):
    """Ficha de reserva del cliente (solo lectura)."""
    from django.urls import reverse
    venta = _venta_desde_token(token)

    estado_label, estado_cls = ESTADO_PAGO_FICHA.get(
        venta.estado_pago, ('Pendiente de pago', 'pen'))

    try:
        tips_texto = _generar_texto_tips(venta, ConfiguracionTips.get_solo())
    except Exception:  # noqa: BLE001 — los tips no deben tumbar la ficha
        logger.exception('[ficha] no se pudieron generar los tips de la reserva %s', venta.id)
        tips_texto = ''

    context = {
        'venta': venta,
        'numero': venta.id,
        'cliente': venta.cliente,
        'estado_label': estado_label,
        'estado_cls': estado_cls,
        'lineas': _lineas_servicios(venta),
        'total_str': _clp(venta.total),
        'pagado_str': _clp(venta.pagado),
        'saldo': int(venta.saldo_pendiente or 0),
        'saldo_str': _clp(venta.saldo_pendiente),
        'tips_texto': tips_texto,
        'comanda_bloqueada': venta.estado_reserva == 'checkout',
        # endpoint que refresca el token de comanda al vuelo y redirige al menú del cliente
        'comanda_url': reverse('ventas:ficha_reserva_comanda', kwargs={'token': token}),
    }
    return render(request, 'ventas/ficha_reserva_cliente.html', context)


def _obtener_o_crear_comanda(venta):
    """Comanda borrador del cliente con token válido (refresca/crea si hace falta).
    Espeja la lógica del admin (generar_link_comanda_ajax) para no duplicar criterios."""
    from django.contrib.auth import get_user_model
    from ..models import Comanda

    comanda = Comanda.objects.filter(
        venta_reserva=venta,
        token_acceso__isnull=False,
        creada_por_cliente=True,
    ).first()
    if comanda and comanda.es_link_valido():
        return comanda
    if comanda:
        comanda.generar_token_acceso()
        return comanda
    User = get_user_model()
    usuario = (User.objects.filter(username='Deborah').first()
               or User.objects.filter(is_superuser=True).first())
    comanda = Comanda.objects.create(
        venta_reserva=venta,
        estado='borrador',
        creada_por_cliente=True,
        usuario_solicita=usuario,
    )
    comanda.generar_token_acceso()
    return comanda


def ficha_comanda(request, token):
    """Botón 3: lleva a la comanda del cliente (la que ya existe), refrescando el
    token al vuelo. Bloqueada una vez hecho el checkout (regla de Jorge)."""
    venta = _venta_desde_token(token)
    if venta.estado_reserva == 'checkout':
        # Ya hizo checkout: la comanda queda cerrada, se vuelve a la ficha.
        return redirect('ventas:ficha_reserva_cliente', token=token)
    comanda = _obtener_o_crear_comanda(venta)
    return redirect(comanda.obtener_url_cliente())
