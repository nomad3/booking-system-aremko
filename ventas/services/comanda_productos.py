# -*- coding: utf-8 -*-
"""La comanda que nace sola cuando una reserva tiene productos para cocina.

Hasta el 19-09-2026 esta regla vivía dentro de `VentaReservaAdmin.save_related`,
o sea que solo corría al GUARDAR LA RESERVA EN EL ADMIN DE DJANGO. La tarjeta
móvil agregaba el producto a la reserva y nunca la llamaba: el producto quedaba
vendido y sumado al total, pero sin comanda. Cocina no se enteraba.

Caso que lo destapó (Jorge, reserva de prueba 6859): Deborah guardó la reserva
en el admin con la tina —el sistema revisó, no había productos, anotó «sin
productos por cubrir»— y después agregaron un café desde la tarjeta. Nadie
volvió a revisar.

Ahora la regla vive acá y la llaman los dos caminos, para que hagan EXACTAMENTE
lo mismo. El admin conserva su aviso en pantalla; la tarjeta devuelve el número
de comanda en su respuesta.
"""
import logging
from datetime import datetime

from django.utils import timezone

logger = logging.getLogger(__name__)

# Comandas que NO cubren un producto: carritos de WhatsApp sin concretar y las
# canceladas (mismo criterio que la columna estado_comanda del inline del admin).
ESTADOS_QUE_NO_CUBREN = ('cancelada', 'borrador', 'pendiente_pago', 'pago_fallido')


def se_prepara_en_cocina(producto):
    """¿Este "producto" es algo que alguien tiene que preparar y entregar?

    Se destapó cerrando las 83 comandas viejas (Jorge, 2026-08-03): entre los
    pedidos había **316 "Gift Cards"**, un "Producto temporal para pago
    giftcard" y líneas de "Descuento -1000". Nada de eso se prepara en cocina.
    Ensuciaba dos cosas a la vez: la agenda —pedidos que nadie debe atender— y
    el inventario, porque al cerrarlas se descontaba stock de algo que no existe
    físicamente.

    Se reutiliza `CATEGORIAS_PRODUCTO_INTERNAS` (la misma lista de H-088 que ya
    filtra el catálogo de la bandeja) en vez de escribir otra: dos listas de lo
    mismo se desincronizan siempre, y la primera vez que pase nadie se va a dar
    cuenta.
    """
    from ventas.views.luna_api_views import CATEGORIAS_PRODUCTO_INTERNAS

    if producto is None:
        return False

    categoria = getattr(getattr(producto, 'categoria', None), 'nombre', '') or ''
    if categoria.strip() in CATEGORIAS_PRODUCTO_INTERNAS:
        return False

    # La categoría no siempre alcanza: "Producto temporal para pago giftcard"
    # puede vivir en cualquier parte, y los descuentos a veces solo se delatan
    # por el nombre o por venir en negativo.
    nombre = str(producto.nombre or '').strip().lower()
    if not nombre:
        return False
    if any(t in nombre for t in ('descuento', 'dto', 'giftcard', 'gift card')):
        return False
    if nombre.startswith('-'):
        return False
    try:
        if float(producto.precio_base or 0) < 0:
            return False
    except (TypeError, ValueError):
        pass
    return True


def asegurar_comanda_de_productos(venta, usuario=None, origen='Admin'):
    """Si la reserva tiene productos de cocina que ninguna comanda cubre, crea UNA
    comanda Pendiente con ellos. Devuelve la comanda creada, o None si no hizo falta.

    `origen` queda escrito en las notas de la comanda («[Admin]», «[Tarjeta]») para
    que en la agenda se sepa por dónde entró el pedido.
    """
    from ventas.models import Comanda, DetalleComanda

    if not venta or not venta.pk:
        return None

    # Editar una reserva ya pasada no debe crear comandas (histórico).
    ultimo = venta.reservaservicios.order_by('-fecha_agendamiento').first()
    if ultimo and ultimo.fecha_agendamiento and ultimo.fecha_agendamiento < timezone.localdate():
        logger.info("Comanda auto: reserva #%s omitida (último servicio %s ya pasó)",
                    venta.pk, ultimo.fecha_agendamiento)
        return None

    cubiertos = set(
        DetalleComanda.objects
        .filter(comanda__venta_reserva=venta)
        .exclude(comanda__estado__in=ESTADOS_QUE_NO_CUBREN)
        .values_list('producto_id', flat=True)
    )

    faltantes = []
    for rp in venta.reservaproductos.select_related('producto', 'producto__categoria'):
        p = rp.producto
        if not p or rp.producto_id in cubiertos:
            continue
        if not se_prepara_en_cocina(p):
            continue
        faltantes.append(rp)

    if not faltantes:
        logger.info(
            "Comanda auto: reserva #%s sin productos por cubrir (cubiertos por comanda: %s)",
            venta.pk, sorted(cubiertos) or 'ninguno — la reserva no tiene productos de cocina',
        )
        return None

    # Fecha objetivo: el primer servicio agendado de la reserva (si hay).
    objetivo = None
    primero = venta.reservaservicios.order_by('fecha_agendamiento', 'hora_inicio').first()
    if primero and primero.fecha_agendamiento:
        try:
            objetivo = timezone.make_aware(datetime.strptime(
                f"{primero.fecha_agendamiento} {primero.hora_inicio or '12:00'}",
                '%Y-%m-%d %H:%M'))
        except (ValueError, TypeError):
            objetivo = None

    comanda = Comanda.objects.create(
        venta_reserva=venta,
        estado='pendiente',
        usuario_solicita=usuario if getattr(usuario, 'is_authenticated', False) else None,
        fecha_entrega_objetivo=objetivo,
        notas_generales=f'[{origen}] Comanda creada automáticamente por productos de la reserva',
    )
    for rp in faltantes:
        DetalleComanda.objects.create(
            comanda=comanda,
            producto=rp.producto,
            cantidad=rp.cantidad,
            precio_unitario=rp.precio_unitario_venta or rp.producto.precio_base or 0,
        )
    logger.info("Comanda auto: creada #%s para reserva #%s con %s producto(s) [%s]",
                comanda.id, venta.pk, len(faltantes), origen)
    return comanda
