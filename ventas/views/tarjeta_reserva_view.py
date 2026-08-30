"""Tarjeta de Reserva — la reserva en el celular (Fase 1: lectura + copiar Pase).

El admin de Django es insufrible en un teléfono: tablas anchas, selects
diminutos, y cada guardado reenvía y revalida el formulario COMPLETO con todos
sus inlines. Esta tarjeta es la alternativa móvil: una pantalla liviana, la
plata primero, y botones que hacen UNA cosa cada uno.

Fase 1 (Jorge, 2026-08-30): solo lectura + botón que COPIA el mensaje del Pase
sin mostrarlo — Deborah lo pega en el cajón de la bandeja omnicanal. Las fases
siguientes agregan pago, producto y servicio con guardados chicos e
independientes; nada de eso vive todavía acá.

La vista es deliberadamente liviana: tres queries con select_related y ningún
cálculo — total/pagado/saldo son campos almacenados. Nada de ficha 360.
"""
from __future__ import annotations

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, render

from ventas.models import VentaReserva
from ventas.views.ficha_reserva_view import mensaje_pase


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff."""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def tarjeta_reserva(request, venta_id):
    venta = get_object_or_404(
        VentaReserva.objects.select_related('cliente'), pk=venta_id)

    servicios = venta.reservaservicios.select_related('servicio').order_by(
        'fecha_agendamiento', 'hora_inicio', 'id')
    productos = venta.reservaproductos.select_related('producto')
    pagos = venta.pagos.order_by('fecha_pago')

    return render(request, 'ventas/tarjeta_reserva.html', {
        'venta': venta,
        'servicios': servicios,
        'productos': productos,
        'pagos': pagos,
        'mensaje_pase': mensaje_pase(venta),
        'debe': int(venta.saldo_pendiente or 0) > 0,
    })
