"""Conexión-Masajes — generación de participantes de masaje por reserva.

Cuando una reserva tiene un servicio de masaje (cantidad_personas >= 1) se crea un
ParticipanteMasajeReserva por persona, para que CADA quien reciba masaje tenga su
ficha de bienestar — incluido el masaje individual. El comprador
(VentaReserva.cliente) queda como primer participante; el resto como 'acompanante'
(a completar luego).

Idempotente: no duplica participantes si ya existen.
"""

import logging
from django.db import transaction

logger = logging.getLogger(__name__)


def reserva_tiene_masaje(venta_reserva):
    """True si la reserva tiene al menos un masaje (cantidad_personas >= 1)."""
    return venta_reserva.reservaservicios.filter(
        servicio__tipo_servicio='masaje',
        cantidad_personas__gte=1,
    ).exists()


def generar_participantes_masaje(venta_reserva):
    """Crea los ParticipanteMasajeReserva faltantes para la reserva. Devuelve la
    lista de los creados (vacía si no aplica o ya estaban todos).

    Aplica a masajes de 1 o más personas: para 1 persona crea solo al comprador
    (su propia ficha); para 2+ crea comprador + acompañantes."""
    from ..models import ParticipanteMasajeReserva

    masajes = venta_reserva.reservaservicios.filter(
        servicio__tipo_servicio='masaje',
        cantidad_personas__gte=1,
    )
    if not masajes.exists():
        return []

    # Nº de personas que reciben masaje (para parejas suele ser un servicio con
    # cantidad_personas=2). Tomamos el máximo entre los masajes de la reserva.
    cantidad = max(m.cantidad_personas for m in masajes)

    with transaction.atomic():
        existentes = list(
            ParticipanteMasajeReserva.objects.select_for_update()
            .filter(reserva=venta_reserva)
        )
        if len(existentes) >= cantidad:
            return []

        creados = []
        tiene_comprador = any(p.tipo_participante == 'comprador' for p in existentes)
        if not tiene_comprador and getattr(venta_reserva, 'cliente_id', None):
            cli = venta_reserva.cliente
            creados.append(ParticipanteMasajeReserva.objects.create(
                reserva=venta_reserva,
                cliente=cli,
                nombre=(cli.nombre or '')[:160],
                telefono=(cli.telefono or '')[:30],
                email=(cli.email or '')[:254],
                tipo_participante='comprador',
            ))

        faltan = cantidad - (len(existentes) + len(creados))
        for _ in range(max(0, faltan)):
            creados.append(ParticipanteMasajeReserva.objects.create(
                reserva=venta_reserva,
                tipo_participante='acompanante',
            ))

        if creados:
            logger.info(
                "[Masajes] %d participante(s) creado(s) para reserva %s",
                len(creados), getattr(venta_reserva, 'id', '?'),
            )
        return creados
