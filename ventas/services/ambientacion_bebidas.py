"""
Fase 2 — Bebidas de la Experiencia Romántica.

La ambientación incluye una bebida (sin costo, excluyente): 2 jugos, o 1 vino,
o 1 espumante, o 2 aguas. Se descuentan del inventario EN LA FECHA DE LA VISITA
(no al reservar) — para eso las líneas van vía una Comanda con
`fecha_entrega_objetivo` = fecha de la tina; el cron `procesar_entregas_comandas_vencidas`
marca la entrega ese día y recién ahí se descuenta el stock.

IDs de productos REALES (prod) — mapeo confirmado con Jorge. No se crean, ya existen.
"""
import logging
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

# Marca en notas_generales para reconocer la comanda de bebida de la ambientación.
MARCA_BEBIDA = '[Ambientación · bebida incluida]'

# Producto IDs reales (prod). Las bebidas van a $0 en la ambientación (solo inventario).
JUGOS = {'frambuesa': 108, 'arandano': 107, 'melon': 109}
AGUAS = {'con_gas': 125, 'sin_gas': 126}
VINO_ID = 20            # Botella Vino Ambientación
ESPUMANTE_ID = 15       # Espumante
CHOCOLATES_ID = 42      # Caja Chocolate ($16.000, el único cobrado)

# Bebida por defecto: 2 jugos (frambuesa + arándano).
DEFAULT_BEBIDA = [JUGOS['frambuesa'], JUGOS['arandano']]

NOMBRE_CAT_AMBIENTACION = 'ambientaciones'


def venta_tiene_ambientacion(venta):
    """True si la reserva incluye un servicio de la categoría Ambientaciones."""
    return venta.reservaservicios.filter(
        servicio__categoria__nombre__iexact=NOMBRE_CAT_AMBIENTACION
    ).exists()


def _fecha_objetivo(venta):
    """Fecha/hora de la visita: la de la tina si existe, si no el primer servicio con fecha."""
    tina = venta.reservaservicios.filter(
        servicio__tipo_servicio='tina', fecha_agendamiento__isnull=False
    ).first()
    ref = tina or venta.reservaservicios.exclude(fecha_agendamiento__isnull=True).first()
    if not ref:
        return timezone.now()
    try:
        naive = datetime.strptime(
            f"{ref.fecha_agendamiento} {ref.hora_inicio or '12:00'}", '%Y-%m-%d %H:%M')
    except (ValueError, TypeError):
        naive = datetime.strptime(f"{ref.fecha_agendamiento} 12:00", '%Y-%m-%d %H:%M')
    return timezone.make_aware(naive)


def _comanda_bebida_existente(venta):
    return venta.comandas.filter(notas_generales__icontains=MARCA_BEBIDA).first()


def asegurar_comanda_bebida_default(venta, productos_ids=None):
    """
    Idempotente: si la reserva tiene ambientación y aún no tiene comanda de bebida,
    crea una con la bebida indicada (default = 2 jugos frambuesa+arándano) a $0.
    Devuelve la Comanda (nueva o existente) o None si no aplica.

    productos_ids: lista de IDs de Producto a poner (para la personalización de F2-C).
                   Si es None, usa el default.
    """
    from ..models import Comanda, DetalleComanda, ReservaProducto, Producto

    if not venta_tiene_ambientacion(venta):
        return None

    existente = _comanda_bebida_existente(venta)
    if existente is not None:
        return existente  # ya tiene su bebida — no duplicar

    ids = productos_ids or DEFAULT_BEBIDA
    comanda = Comanda.objects.create(
        venta_reserva=venta,
        estado='pendiente',
        fecha_entrega_objetivo=_fecha_objetivo(venta),
        notas_generales=f'{MARCA_BEBIDA} (incluida, sin costo)',
    )
    for pid in ids:
        try:
            producto = Producto.objects.get(id=pid)
        except Producto.DoesNotExist:
            logger.warning('[ambientacion_bebidas] producto %s no existe, se omite', pid)
            continue
        # Precio 0: la bebida es incluida; solo mueve inventario, no suma al total.
        DetalleComanda.objects.create(
            comanda=comanda, producto=producto, cantidad=1, precio_unitario=0)
        ReservaProducto.objects.create(
            venta_reserva=venta, producto=producto, cantidad=1,
            precio_unitario_venta=0)  # fecha_entrega = NULL → no descuenta hasta la visita
    logger.info('[ambientacion_bebidas] comanda de bebida creada para reserva %s (productos %s)',
                venta.id, ids)
    return comanda
