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


def mapear_participante_a_linea(venta_reserva):
    """Empareja cada participante con su línea de masaje (ReservaServicio).

    Se arman "slots" por persona: cada línea aporta `cantidad_personas` slots. Los
    participantes (comprador primero, luego acompañantes por id) se asignan en
    orden a esos slots. Devuelve {participante_id: ReservaServicio|None}.

    Permite saber qué masajista (línea.proveedor_asignado) atiende a cada persona
    sin necesidad de un campo nuevo en la BD.
    """
    lineas = list(
        venta_reserva.reservaservicios
        .filter(servicio__tipo_servicio='masaje', cantidad_personas__gte=1)
        .select_related('proveedor_asignado')
        .order_by('id')
    )
    slots = []
    for ls in lineas:
        for _ in range(ls.cantidad_personas or 1):
            slots.append(ls)

    participantes = sorted(
        venta_reserva.participantes_masaje.all(),
        key=lambda p: (0 if p.tipo_participante == 'comprador' else 1, p.id),
    )
    mapeo = {}
    for i, p in enumerate(participantes):
        if slots:
            mapeo[p.id] = slots[i] if i < len(slots) else slots[-1]
        else:
            mapeo[p.id] = None
    return mapeo

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

    # Nº TOTAL de personas que reciben masaje = SUMA de las líneas de masaje.
    # Cubre las dos formas de cargar una reserva de pareja:
    #   - 1 línea con cantidad_personas=2  → 2 personas
    #   - 2 líneas con cantidad_personas=1 → 2 personas (lo más frecuente)
    cantidad = sum((m.cantidad_personas or 1) for m in masajes)

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


def sincronizar_participantes_masaje(venta_reserva):
    """Ajusta a la baja los participantes cuando se quitan líneas de masaje.

    target = suma de cantidad_personas de las líneas de masaje (0 si no quedan).
    Si hay más participantes que target, elimina los SOBRANTES que NO tengan ficha
    completada (acompañantes primero, luego comprador). NUNCA borra un participante
    con ficha completada (preserva el dato). Devuelve cuántos eliminó."""
    from ..models import ParticipanteMasajeReserva

    masajes = venta_reserva.reservaservicios.filter(
        servicio__tipo_servicio='masaje', cantidad_personas__gte=1,
    )
    target = sum((m.cantidad_personas or 1) for m in masajes)

    participantes = list(
        ParticipanteMasajeReserva.objects.filter(reserva=venta_reserva)
    )
    sobran = len(participantes) - target
    if sobran <= 0:
        return 0

    # Solo se pueden quitar los que NO tienen ficha completada.
    removibles = [
        p for p in participantes
        if not p.ficha_bienestar_id and p.estado_contacto != 'ficha_completada'
    ]
    # Acompañantes primero (id como desempate estable).
    removibles.sort(key=lambda p: (0 if p.tipo_participante == 'acompanante' else 1, p.id))

    eliminados = 0
    for p in removibles[:sobran]:
        p.delete()
        eliminados += 1
    if eliminados:
        logger.info(
            "[Masajes] %d participante(s) sobrante(s) eliminado(s) de reserva %s",
            eliminados, getattr(venta_reserva, 'id', '?'),
        )
    return eliminados
