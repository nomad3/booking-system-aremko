"""H-078 — Rollback del estado de venta en turnos ESCALADOS del agente.

Invariante: si el turno del agente NO produce mensaje para el cliente (escalar=True:
el guardián frenó el texto y lo revisa un humano), el estado de venta de esa
conversación (carrito + propuesta pendiente) debe quedar EXACTAMENTE como estaba al
inicio del turno. Un turno sin mensaje no deja residuo.

Caso real que motiva esto (2026-07-29, conversación de prueba de Jorge): mientras
"armaba" las opciones de la Pausa, el agente agregó la Tina Hornopiren al carrito y
recién después su texto fue frenado por el guardián H-045 → el mensaje nunca salió,
pero la tina fantasma quedó en el carrito (visible en la bandeja, lista para
desincronizar el cierre cuando el cliente eligiera la otra opción).

Diseño: snapshot EN MEMORIA al inicio del turno (deepcopy de los JSON; sin tablas
nuevas ni migraciones) y restauración condicional al final. La restauración es
best-effort e idempotente: nunca debe romper el turno (errores → log y seguir).
"""
import copy
import logging

logger = logging.getLogger(__name__)

# Campos de CarritoReserva que un turno puede mutar (identidad y timestamps quedan fuera;
# expires_at tampoco se restaura: alargar la vida del carrito es inofensivo).
_CAMPOS_CARRITO = (
    'items', 'estado', 'subtotal_servicios', 'subtotal_productos',
    'descuento_combo', 'packs_aplicados', 'total',
)
# Campos de PropuestaReserva que las tools editan (agregar_servicio/producto_a_propuesta).
_CAMPOS_PROPUESTA = ('payload', 'servicios', 'total', 'resumen_texto', 'estado')


def snapshot_estado_venta(canal, external_id):
    """Captura el carrito y la propuesta 'pendiente' más reciente de la conversación.

    Devuelve un dict apto para `restaurar_estado_venta`. None en 'carrito'/'propuesta'
    significa "no existía al inicio del turno".
    """
    from carrito_reservas.models import CarritoReserva
    from .models import PropuestaReserva

    carrito = CarritoReserva.objects.filter(canal=canal, external_id=external_id).first()
    propuesta = (PropuestaReserva.objects
                 .filter(canal=canal, external_id=external_id, estado='pendiente')
                 .order_by('-created_at').first())
    snap = {'carrito': None, 'propuesta': None}
    if carrito is not None:
        snap['carrito'] = {'pk': carrito.pk}
        for campo in _CAMPOS_CARRITO:
            snap['carrito'][campo] = copy.deepcopy(getattr(carrito, campo))
    if propuesta is not None:
        snap['propuesta'] = {'pk': propuesta.pk}
        for campo in _CAMPOS_PROPUESTA:
            snap['propuesta'][campo] = copy.deepcopy(getattr(propuesta, campo))
    return snap


def restaurar_estado_venta(canal, external_id, snap):
    """Restaura carrito + propuesta al snapshot. Devuelve True si algo se revirtió.

    Best-effort: cada mitad se restaura por separado y los errores se loguean sin
    propagarse (restaurar nunca debe romper el flujo del agente).
    """
    snap = snap or {}
    revertido = False
    try:
        revertido = _restaurar_carrito(canal, external_id, snap.get('carrito')) or revertido
    except Exception:  # noqa: BLE001 — best effort
        logger.exception('[rollback H-078] fallo restaurando carrito %s:%s', canal, external_id)
    try:
        revertido = _restaurar_propuesta(canal, external_id, snap.get('propuesta')) or revertido
    except Exception:  # noqa: BLE001 — best effort
        logger.exception('[rollback H-078] fallo restaurando propuesta %s:%s', canal, external_id)
    return revertido


def _restaurar_carrito(canal, external_id, prev):
    from carrito_reservas.models import CarritoReserva

    actual = CarritoReserva.objects.filter(canal=canal, external_id=external_id).first()
    if prev is None:
        if actual is None:
            return False
        # El turno creó un carrito que no existía → se elimina completo.
        actual.delete()
        return True
    if actual is None:
        # El turno eliminó el carrito (raro en un turno escalado) → se recrea igual al snapshot.
        CarritoReserva.objects.create(
            canal=canal, external_id=external_id,
            **{campo: prev[campo] for campo in _CAMPOS_CARRITO})
        return True
    if all(getattr(actual, campo) == prev[campo] for campo in _CAMPOS_CARRITO):
        return False
    for campo in _CAMPOS_CARRITO:
        setattr(actual, campo, prev[campo])
    actual.save()
    return True


def _restaurar_propuesta(canal, external_id, prev):
    from .models import PropuestaReserva

    pendientes = PropuestaReserva.objects.filter(
        canal=canal, external_id=external_id, estado='pendiente')
    revertido = False
    if prev is None:
        # Cualquier pendiente presente la creó este turno (el cliente nunca vio nada) → descartar.
        for p in pendientes:
            p.estado = 'descartada'
            p.save(update_fields=['estado'])
            revertido = True
        return revertido
    # Pendientes NUEVAS creadas por el turno (además de la que ya existía) → descartar.
    for p in pendientes.exclude(pk=prev['pk']):
        p.estado = 'descartada'
        p.save(update_fields=['estado'])
        revertido = True
    obj = PropuestaReserva.objects.filter(pk=prev['pk']).first()
    if obj is None:
        return revertido
    if any(getattr(obj, campo) != prev[campo] for campo in _CAMPOS_PROPUESTA):
        for campo in _CAMPOS_PROPUESTA:
            setattr(obj, campo, prev[campo])
        obj.save(update_fields=list(_CAMPOS_PROPUESTA))
        revertido = True
    return revertido
