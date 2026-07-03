# -*- coding: utf-8 -*-
"""Agregar servicios/productos a una VentaReserva YA CREADA (H-060).

Fuente única para (a) el endpoint HTTP agregar_servicios_reserva y (b) la aprobación
de una PropuestaReserva con reserva_existente_id (aprobar_adicion_a_reserva_existente
en ventas/views/luna_api_views.py). Antes esta lógica vivía duplicada/inline dentro
de agregar_servicios_reserva con 2 bugs:

1. Nunca llamaba actualizar_saldo() — si la reserva ya estaba 'pagado' y se agregaba
   algo nuevo sin pagar, saldo_pendiente subía pero estado_pago se quedaba pegado en
   'pagado' (no bajaba a 'parcial').
2. El total recalculado solo sumaba ReservaServicio — los ReservaProducto YA
   existentes en la reserva (ej. de la creación original) se perdían del total.

Ambos se corrigen acá.
"""

from datetime import datetime

from django.utils import timezone

from ventas.models import Servicio, ReservaServicio, Producto, ReservaProducto, Comanda, DetalleComanda
from ventas.services.pack_descuento_service import PackDescuentoService


def agregar_items_a_reserva(venta_reserva, servicios_data, productos_data):
    """Agrega servicios y/o productos a una VentaReserva YA CREADA y recalcula
    total/saldo/estado_pago correctamente.

    servicios_data: [{'servicio_id', 'fecha' (YYYY-MM-DD), 'hora', 'cantidad_personas'}, ...]
    productos_data: [{'producto_id', 'cantidad'}, ...]

    Productos: replica el MISMO patrón de 3 tablas que usa crear_reserva (Comanda +
    DetalleComanda para que aparezca en cocina, + ReservaProducto con fecha_entrega=NULL
    — el inventario se descuenta recién al ENTREGAR, no al vender).

    Devuelve un dict con servicios_agregados/productos_agregados/descuentos_aplicados/
    nuevo_total/saldo_pendiente/estado_pago. Lanza Servicio.DoesNotExist si algún
    servicio_id no existe (el caller lo traduce a Response); un producto_id inexistente
    se ignora (no debe tumbar el resto de la operación, mismo criterio que crear_reserva).
    """
    servicios_data = servicios_data or []
    productos_data = productos_data or []

    servicios_agregados = []
    for servicio_data in servicios_data:
        servicio = Servicio.objects.get(id=servicio_data['servicio_id'])
        fecha = datetime.strptime(servicio_data['fecha'], '%Y-%m-%d').date()
        hora = servicio_data['hora']
        cantidad_personas = servicio_data['cantidad_personas']
        precio_unitario = servicio.precio_base

        reserva_servicio = ReservaServicio.objects.create(
            venta_reserva=venta_reserva,
            servicio=servicio,
            fecha_agendamiento=fecha,
            hora_inicio=hora,
            cantidad_personas=cantidad_personas,
            precio_unitario_venta=precio_unitario,
        )
        subtotal = reserva_servicio.calcular_precio()
        servicios_agregados.append({
            'id': reserva_servicio.id,
            'servicio_id': servicio.id,
            'servicio_nombre': servicio.nombre,
            'fecha': servicio_data['fecha'],
            'hora': hora,
            'cantidad_personas': cantidad_personas,
            'precio_unitario': float(precio_unitario),
            'subtotal': float(subtotal),
        })

    productos_agregados = []
    if productos_data:
        # fecha_entrega_objetivo: primer ReservaServicio (por fecha+hora) de TODA la reserva
        # ya actualizada (viejos + nuevos) — cuándo el cliente estará físicamente en el spa,
        # no cuándo se agregó el producto. Mismo criterio que crear_reserva.
        lineas_servicio = list(
            venta_reserva.reservaservicios.all().order_by('fecha_agendamiento', 'hora_inicio'))
        if lineas_servicio:
            primero = lineas_servicio[0]
            try:
                naive_obj = datetime.strptime(
                    f"{primero.fecha_agendamiento} {primero.hora_inicio or '12:00'}",
                    '%Y-%m-%d %H:%M')
            except (ValueError, TypeError):
                naive_obj = datetime.strptime(f"{primero.fecha_agendamiento} 12:00", '%Y-%m-%d %H:%M')
            fecha_entrega_objetivo = timezone.make_aware(naive_obj)
        else:
            # Reserva sin ningún servicio con fecha (caso raro, ej. solo productos):
            # entregar ahora, no hay una fecha de visita de la que colgarse.
            fecha_entrega_objetivo = timezone.now()

        comanda = Comanda.objects.create(
            venta_reserva=venta_reserva,
            estado='pendiente',
            creada_por_cliente=True,
            fecha_entrega_objetivo=fecha_entrega_objetivo,
            notas_generales='[Luna WhatsApp] Productos agregados a una reserva existente',
        )
        for prod_data in productos_data:
            try:
                producto = Producto.objects.get(id=prod_data['producto_id'])
            except Producto.DoesNotExist:
                continue  # un producto inexistente no debe tumbar el resto de la operación
            cant = int(prod_data.get('cantidad', 1) or 1)
            DetalleComanda.objects.create(
                comanda=comanda, producto=producto, cantidad=cant,
                precio_unitario=producto.precio_base)
            reserva_producto = ReservaProducto.objects.create(
                venta_reserva=venta_reserva, producto=producto, cantidad=cant,
                precio_unitario_venta=producto.precio_base)  # fecha_entrega = NULL
            productos_agregados.append({
                'id': reserva_producto.id,
                'producto_id': producto.id,
                'producto_nombre': producto.nombre,
                'cantidad': cant,
                'subtotal': float(producto.precio_base * cant),
            })

    # Recalcular con TODOS los servicios Y productos de la reserva (viejos + nuevos) — el bug
    # #2 de arriba era que el total recalculado solo sumaba servicios, perdiendo los productos
    # ya existentes en la reserva.
    todos_servicios = []
    for rs in venta_reserva.reservaservicios.all():
        todos_servicios.append({
            'id': rs.servicio.id,
            'nombre': rs.servicio.nombre,
            'precio': float(rs.servicio.precio_base),
            'fecha': rs.fecha_agendamiento.strftime('%Y-%m-%d'),
            'hora': rs.hora_inicio,
            'cantidad_personas': rs.cantidad_personas,
            'tipo_servicio': rs.servicio.tipo_servicio,
            'subtotal': float(rs.calcular_precio()),
        })

    packs_aplicables = PackDescuentoService.detectar_packs_aplicables(
        PackDescuentoService.construir_cart(todos_servicios))
    total_descuentos = sum(pack_info['descuento'] for pack_info in packs_aplicables)

    subtotal_servicios = sum(item['subtotal'] for item in todos_servicios)
    subtotal_productos = sum(
        float(rp.precio_unitario_venta or 0) * rp.cantidad
        for rp in venta_reserva.reservaproductos.all())

    venta_reserva.total = subtotal_servicios + subtotal_productos - total_descuentos
    # FIX del bug #1: actualizar_saldo() recalcula pagado/saldo_pendiente/estado_pago (y
    # guarda) a partir del total recién seteado — antes solo se hacía
    # `saldo_pendiente = total - pagado; save()` sin tocar estado_pago, así que una reserva
    # 'pagado' se quedaba pegada en 'pagado' aunque el saldo pendiente subiera.
    venta_reserva.actualizar_saldo()

    return {
        'servicios_agregados': servicios_agregados,
        'productos_agregados': productos_agregados,
        'descuentos_aplicados': [
            {'pack_nombre': pack_info['pack'].nombre, 'descuento': float(pack_info['descuento'])}
            for pack_info in packs_aplicables
        ],
        'total_descuentos': float(total_descuentos),
        'nuevo_total': float(venta_reserva.total),
        'saldo_pendiente': float(venta_reserva.saldo_pendiente),
        'estado_pago': venta_reserva.estado_pago,
    }
