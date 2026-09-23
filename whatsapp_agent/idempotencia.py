"""Qué hacer cuando Luna pide una propuesta con una clave que ya se usó (P-49).

La clave de idempotencia existe para que un reintento del modelo en el mismo
turno no duplique la propuesta. Pero las claves que arman las herramientas son
estables por cliente, no por pedido:

- ``carrito-<id>``: el carrito es UNO por cliente y se reusa en cada compra
  (se vacía al crear la reserva, pero conserva su id);
- ``ritual-<tel>-<fecha>``, ``refugio-…``, ``dia-…``: la misma fecha se puede
  volver a pedir después de que la propuesta venció o se descartó;
- ``gc-<tel>-<experiencia>-<n>``: la misma gift card se puede volver a comprar.

Y las herramientas que no mandan clave (agregar a una reserva existente, la
herramienta genérica) guardaban la cadena vacía, que la restricción unique deja
existir UNA sola vez: desde la fila vacía del 19-06-2026, agregar algo a una
reserva desde WhatsApp nunca funcionó.

En todos esos casos la base respondía «duplicate key» y el cliente recibía un
error interno. Acá se decide ANTES de crear:

- hay una propuesta pendiente y viva de esa familia de claves → es un
  reintento: se devuelve esa (como siempre);
- el mismo pedido se convirtió en reserva hace poco y la reserva sigue ahí →
  se avisa que ya está hecha, en vez de cotizar de nuevo;
- cualquier otro caso es un pedido nuevo → se crea con una clave libre
  (``carrito-7#2``, ``#3``…).
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from whatsapp_agent.models import PropuestaReserva

logger = logging.getLogger(__name__)

SEPARADOR = '#'
# El campo mide 255; se deja espacio para el sufijo «#n».
LARGO_BASE = 240

# Un pedido idéntico a uno que se convirtió en reserva hace menos de esto es un
# reintento, no una compra nueva. Pasado ese plazo se cotiza de nuevo: en el
# peor caso Deborah ve una propuesta repetida (y al aprobarla la disponibilidad
# la frena), que es mucho mejor que negarle la venta a un cliente que vuelve.
VENTANA_REINTENTO = timedelta(hours=24)


def huella(payload) -> str:
    """Lo que se pidió —servicios, productos, gift cards—, sin los datos del cliente."""
    p = payload or {}
    return json.dumps({'servicios': p.get('servicios') or [],
                       'productos': p.get('productos') or [],
                       'giftcards': p.get('giftcards') or []},
                      sort_keys=True, default=str)


@dataclass
class Decision:
    """`vigente`: devolver `propuesta`. `creada`: el pedido ya es la reserva
    `propuesta.reserva_id`. `nueva`: crear con `clave`."""
    tipo: str
    propuesta: Optional[PropuestaReserva] = None
    clave: str = ''


def _reserva_sigue_en_pie(reserva_id) -> bool:
    """Cancelar una reserva hoy es borrarla; si la borraron, el pedido es nuevo."""
    from ventas.models import VentaReserva
    return (VentaReserva.objects.filter(pk=reserva_id)
            .exclude(estado_reserva='cancelada').exclude(estado_pago='cancelado')
            .exists())


def resolver(idempotency_key, payload, *, canal, external_id,
             reserva_existente_id=None, propuesta_id='') -> Decision:
    """Decide, antes de crear, si el pedido es un reintento o uno nuevo."""
    ahora = timezone.now()
    pedido = huella(payload)

    if not idempotency_key:
        # Sin clave, el reintento se reconoce por el pedido mismo: una propuesta
        # pendiente y viva de esta conversación, para la misma reserva (o para
        # ninguna), con exactamente lo mismo.
        candidatas = (PropuestaReserva.objects
                      .filter(canal=canal, external_id=external_id, estado='pendiente',
                              reserva_existente_id=reserva_existente_id,
                              expires_at__gt=ahora)
                      .order_by('-created_at')[:20])
        for p in candidatas:
            if huella(p.payload) == pedido:
                return Decision('vigente', p)
        return Decision('nueva', clave=f'auto-{propuesta_id}')

    base = idempotency_key[:LARGO_BASE]
    familia = list(PropuestaReserva.objects
                   .filter(Q(idempotency_key=base)
                           | Q(idempotency_key__startswith=base + SEPARADOR))
                   .order_by('-created_at'))

    for p in familia:
        if p.esta_vigente():
            return Decision('vigente', p)

    for p in familia:
        cuando = p.creada_at or p.created_at
        if (p.estado == 'creada' and p.reserva_id and cuando
                and ahora - cuando < VENTANA_REINTENTO
                and huella(p.payload) == pedido
                and _reserva_sigue_en_pie(p.reserva_id)):
            return Decision('creada', p)

    usadas = {p.idempotency_key for p in familia}
    clave, n = base, 2
    while clave in usadas:
        clave = f'{base}{SEPARADOR}{n}'
        n += 1
    if familia:
        logger.info('[Luna] clave %s ya usada (%s); pedido nuevo con %s', base[:48],
                    ', '.join(sorted({p.estado for p in familia})), clave[-6:])
    return Decision('nueva', clave=clave)


def crear(clave, **campos) -> Optional[PropuestaReserva]:
    """Crea la propuesta con la clave elegida.

    Si otra llamada simultánea tomó la misma clave un instante antes, devuelve
    None en vez de reventar (el punto de guardado deja sana la transacción de
    afuera). Quien llama vuelve a `resolver` y encuentra la que ganó.
    """
    try:
        with transaction.atomic():
            return PropuestaReserva.objects.create(idempotency_key=clave, **campos)
    except IntegrityError:
        logger.warning('[Luna] la clave %s se ocupó mientras se creaba la propuesta', clave[:48])
        return None


def respuesta_ya_creada(propuesta) -> dict:
    """El pedido ya es una reserva: decirlo, no cotizar de nuevo ni fallar."""
    n = propuesta.reserva_id
    solo_regalo = not ((propuesta.payload or {}).get('servicios'))
    if solo_regalo:
        texto = f'Tu compra ya quedó registrada (RES-{n}), no hace falta confirmarla de nuevo 🌿'
    else:
        texto = f'Tu reserva RES-{n} ya está creada con esto mismo, no hace falta confirmarla de nuevo 🌿'
    return {
        'success': True,
        'ya_creada': True,
        'reserva_id': n,
        'propuesta_id': propuesta.propuesta_id,
        'resumen_texto': propuesta.resumen_texto,
        'total': int(propuesta.total or 0),
        # `mensaje` es lo que Luna le copia al cliente; `instruccion`, lo que no.
        'mensaje': texto,
        'instruccion': (
            f'Este pedido YA se convirtió en la reserva RES-{n}. NO armes otra cotización '
            'ni escales. Si el cliente quiere sumar algo, usa agregar_servicio_a_reserva_existente '
            f'o agregar_producto_a_reserva_existente con la reserva {n}.'),
    }


# Dos llamadas simultáneas con la misma clave y ninguna quedó a la vista: raro,
# pero no es motivo para mostrarle un error técnico al cliente.
RESPUESTA_EN_CURSO = {
    'success': False,
    'error': 'propuesta_en_curso',
    'mensaje': 'Estoy terminando de preparar tu cotización, dame un momento 🌿',
    'instruccion': ('Otra llamada está creando esta misma propuesta. No la repitas ni escales: '
                    'espera el próximo mensaje del cliente.'),
}
