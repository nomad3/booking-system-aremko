# -*- coding: utf-8 -*-
"""La operación de venta: una pieza → una línea real en la reserva."""
from datetime import date

from django.db import transaction

from .models import ArtesaniaPieza, producto_generico


class ErrorVenta(Exception):
    """Errores esperables del flujo de venta (mensaje para el usuario)."""


def vender_pieza(codigo, reserva_id, monto=None, usuario=None):
    """Vende una pieza a una reserva. Devuelve (pieza, reserva).

    - Crea el ReservaProducto sobre el producto genérico con
      precio_unitario_venta = precio de la pieza (o el monto ajustado).
    - Marca la pieza vendida (reserva, monto, fecha).
    - Recalcula el total de la reserva (misma mecánica del admin).
    Todo o nada: si algo falla, no queda ni la línea ni la pieza marcada.
    """
    from ventas.models import ReservaProducto, VentaReserva

    try:
        pieza = ArtesaniaPieza.objects.get(codigo=str(codigo).strip())
    except ArtesaniaPieza.DoesNotExist:
        raise ErrorVenta(f'No existe la pieza con código {codigo}.')
    if not pieza.viva:
        raise ErrorVenta(
            f'La pieza {pieza.codigo} no está disponible '
            f'(estado: {pieza.get_estado_display()}).')

    try:
        reserva = VentaReserva.objects.get(id=int(reserva_id))
    except (VentaReserva.DoesNotExist, ValueError, TypeError):
        raise ErrorVenta(f'No existe la reserva #{reserva_id}.')

    monto_final = int(monto) if monto else int(pieza.precio)
    if monto_final <= 0:
        raise ErrorVenta('El monto debe ser mayor que cero.')

    with transaction.atomic():
        # fecha_entrega HOY a propósito: la artesanía se entrega en mano al
        # venderla — así no aparece como "pendiente de entrega" en las agendas
        # de checkout (que persiguen productos con deuda de entrega).
        linea = ReservaProducto.objects.create(
            venta_reserva=reserva,
            producto=producto_generico(),
            cantidad=1,
            precio_unitario_venta=monto_final,
            fecha_entrega=date.today(),
        )
        pieza.venta_linea = linea
        pieza.estado = 'vendida'
        pieza.venta_reserva = reserva
        pieza.venta_monto = monto_final
        pieza.venta_fecha = date.today()
        if usuario:
            pieza.notas = (f'{pieza.notas} · vendida por {usuario}'.strip(' ·'))[:255]
        pieza.save()
        # El total se recalcula con los precios congelados de las líneas —
        # la misma mecánica que usa el admin de reservas.
        reserva.calcular_total()

    return pieza, reserva
