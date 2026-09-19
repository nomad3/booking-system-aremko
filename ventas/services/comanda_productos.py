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

**El segundo café (mismo día).** Todo calzaba por `producto_id`: si una comanda
de la reserva ya tenía UN café, cualquier café de esa reserva se daba por
«cubierto». El segundo no generaba comanda, aparecía «Entregado» apenas se
agregaba —porque la comanda del primero ya lo estaba— y al entregar una comanda
se marcaban TODAS las líneas de ese producto. Ahora se reparte por CANTIDAD
(`repartir_comandas`): cada unidad vendida se asigna a una unidad de comanda, en
orden, y las tres decisiones —qué falta mandar a cocina, qué estado mostrar, qué
línea se entrega— salen de ese mismo reparto.
"""
import logging
from collections import defaultdict
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


# De menos a más avanzado: una línea cubierta por dos comandas muestra la más atrasada.
ORDEN_ESTADOS = ('pendiente', 'pago_confirmado', 'procesando', 'entregada')


def repartir_comandas(venta):
    """Asigna cada unidad vendida de la reserva a una unidad de comanda, en orden.

    Las líneas de producto van por id (el orden en que se vendieron) y las líneas
    de comanda por fecha de solicitud: el primer café vendido se queda con la
    primera comanda que trae un café, el segundo con la siguiente.

    Devuelve una lista, una entrada por ReservaProducto:
        {'linea': rp, 'cubren': [(comanda, unidades), ...], 'sin_cubrir': n}

    No distingue lo que se cobra de lo que viene incluido en una ambientación (el
    espumante de una decoración va en una comanda y no es una línea de la cuenta):
    esas unidades pueden terminar «cubriendo» un espumante comprado aparte. Ya
    pasaba con la regla anterior; resolverlo pide enlazar DetalleComanda con
    ReservaProducto, que es otro trabajo.
    """
    from ventas.models import DetalleComanda

    if not venta or not venta.pk:
        return []
    bolsa = defaultdict(list)            # producto_id → [[comanda, unidades libres], ...]
    detalles = (DetalleComanda.objects
                .filter(comanda__venta_reserva=venta)
                .exclude(comanda__estado__in=ESTADOS_QUE_NO_CUBREN)
                .select_related('comanda')
                .order_by('comanda__fecha_solicitud', 'comanda_id', 'id'))
    for d in detalles:
        bolsa[d.producto_id].append([d.comanda, d.cantidad or 0])

    reparto = []
    lineas = (venta.reservaproductos
              .select_related('producto', 'producto__categoria').order_by('id'))
    for rp in lineas:
        falta, cubren = (rp.cantidad or 0), []
        for par in bolsa.get(rp.producto_id, ()):
            if falta <= 0:
                break
            if par[1] <= 0:
                continue
            usar = min(par[1], falta)
            par[1] -= usar
            falta -= usar
            cubren.append((par[0], usar))
        reparto.append({'linea': rp, 'cubren': cubren, 'sin_cubrir': falta})
    return reparto


def estado_de_linea(item):
    """El estado de cocina de UNA línea, según las comandas que cubren SUS unidades.

    'sin_comanda' si le falta alguna unidad por mandar; si no, el estado más
    atrasado entre las comandas que la cubren.
    """
    if item['sin_cubrir'] > 0 or not item['cubren']:
        return 'sin_comanda'
    estados = [c.estado for c, _ in item['cubren']]
    conocidos = [e for e in estados if e in ORDEN_ESTADOS]
    if not conocidos:
        return estados[0]
    return min(conocidos, key=ORDEN_ESTADOS.index)


def estados_para_mostrar(venta, solo_cocina=False):
    """{id de ReservaProducto: 'pendiente' | 'procesando' | 'entregada'} para pintar.

    La agenda y la tarjeta móvil muestran lo mismo: 'sin_comanda' y
    'pago_confirmado' se ven como 'pendiente' —para quien entrega, las dos cosas
    significan «todavía nadie lo preparó»—.

    Con `solo_cocina=True` se omite lo que no se prepara (gift cards,
    descuentos): en la tarjeta, una gift card con la etiqueta «Pendiente» haría
    pensar que cocina le debe algo al cliente.
    """
    estados = {}
    for item in repartir_comandas(venta):
        rp = item['linea']
        if solo_cocina and not se_prepara_en_cocina(rp.producto):
            continue
        clave = estado_de_linea(item)
        estados[rp.pk] = 'pendiente' if clave in ('sin_comanda', 'pago_confirmado') else clave
    return estados


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

    # Por CANTIDAD, no por tipo de producto: el segundo café de una reserva también
    # llega a cocina aunque ya exista una comanda con un café.
    faltantes = {}                       # producto_id → [producto, unidades, precio]
    for item in repartir_comandas(venta):
        rp = item['linea']
        if item['sin_cubrir'] <= 0 or not rp.producto or not se_prepara_en_cocina(rp.producto):
            continue
        entrada = faltantes.setdefault(
            rp.producto_id,
            [rp.producto, 0, rp.precio_unitario_venta or rp.producto.precio_base or 0])
        entrada[1] += item['sin_cubrir']

    if not faltantes:
        logger.info("Comanda auto: reserva #%s sin unidades por cubrir", venta.pk)
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
    for producto, unidades, precio in faltantes.values():
        DetalleComanda.objects.create(comanda=comanda, producto=producto,
                                      cantidad=unidades, precio_unitario=precio)
    logger.info("Comanda auto: creada #%s para reserva #%s con %s producto(s) [%s]",
                comanda.id, venta.pk, len(faltantes), origen)
    return comanda
