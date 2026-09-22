"""Qué líneas de servicio ocupan de verdad un horario.

Una reserva cancelada no ocupa nada. Pero el código la marca de dos formas
según la pantalla: `estado_reserva='cancelada'` (agenda operativa, iCal,
bloqueos de servicio) y `estado_pago='cancelado'` (calendario matriz,
métricas). Los caminos que DECIDEN disponibilidad —vitrina web, Luna, tarjeta
móvil, checkout y la señal de ReservaServicio— no miraban ninguna de las dos,
así que una reserva cancelada seguía bloqueando su hora.

Hoy en la práctica cancelar es borrar la reserva (22-09-2026: en toda la base
hay una sola venta marcada cancelada), por eso nadie lo notó. Este módulo es
el único lugar donde vive la regla, para que el día en que exista una
cancelación que conserve la historia todos los caminos la respeten igual.
"""
from django.db.models import Q

# Las dos marcas que el resto del código ya usa para "esta venta se canceló".
VENTA_CANCELADA = (Q(venta_reserva__estado_reserva='cancelada')
                   | Q(venta_reserva__estado_pago='cancelado'))


def lineas_vigentes(queryset=None):
    """Las ReservaServicio que cuentan para la ocupación: sin las canceladas.

    Sin argumento parte de todas las líneas; con un queryset lo filtra.
    """
    from ventas.models import ReservaServicio
    base = ReservaServicio.objects.all() if queryset is None else queryset
    return base.exclude(VENTA_CANCELADA)
