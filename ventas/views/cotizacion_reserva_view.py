"""
Vista para generar cotizaciones de reserva.
Muestra servicios, productos y giftcards con sus valores sin información de pago.
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from ..models import VentaReserva


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def generar_cotizacion(request, reserva_id):
    """
    Vista para generar la cotización de reserva.
    Muestra el texto generado en un textarea editable para copiar/enviar.
    """
    reserva = get_object_or_404(VentaReserva, id=reserva_id)

    # Generar el texto de la cotización
    texto_cotizacion = _generar_texto_cotizacion(reserva)

    context = {
        'reserva': reserva,
        'texto_cotizacion': texto_cotizacion,
    }

    return render(request, 'ventas/cotizacion.html', context)


def _generar_texto_cotizacion(reserva):
    """
    Genera el texto de la cotización con servicios, productos y giftcards.

    Args:
        reserva: Instancia de VentaReserva

    Returns:
        str: Texto de la cotización formateado
    """
    lineas = []

    # Encabezado
    lineas.append("🌿 COTIZACIÓN AREMKO 🌿")
    lineas.append("")
    lineas.append(f"Cotización Nº {reserva.id}")
    lineas.append(f"Cliente: {reserva.cliente.nombre}")
    lineas.append("")
    lineas.append("━" * 12)
    lineas.append("")

    # Obtener servicios, productos y giftcards
    servicios = reserva.reservaservicios.all().select_related('servicio', 'servicio__categoria')
    productos = reserva.reservaproductos.all().select_related('producto')
    giftcards = reserva.giftcards.all()

    # Servicios contratados
    if servicios:
        lineas.append("📋 SERVICIOS")
        lineas.append("")

        # Listar TODOS los servicios con fecha, hora y personas
        servicios_ordenados = sorted(servicios, key=lambda s: (s.fecha_agendamiento, s.hora_inicio or ''))

        for servicio_reserva in servicios_ordenados:
            nombre = servicio_reserva.servicio.nombre
            personas = servicio_reserva.cantidad_personas or 1
            fecha = servicio_reserva.fecha_agendamiento.strftime('%d/%m/%Y')

            # Usar precio congelado si existe, sino precio_base
            precio_unitario = (servicio_reserva.precio_unitario_venta
                             if servicio_reserva.precio_unitario_venta
                             else servicio_reserva.servicio.precio_base)
            subtotal = precio_unitario * personas

            # Formatear hora
            hora_texto = ""
            if servicio_reserva.hora_inicio:
                hora_texto = f" - {servicio_reserva.hora_inicio} hrs"

            # No mostrar personas para Desayuno
            if 'desayuno' in nombre.lower():
                lineas.append(f"• {nombre}")
                lineas.append(f"  Fecha: {fecha}{hora_texto}")
                lineas.append(f"  Valor: ${int(subtotal):,}")
            else:
                lineas.append(f"• {nombre}")
                lineas.append(f"  Fecha: {fecha}{hora_texto}")
                lineas.append(f"  Personas: {personas}")
                lineas.append(f"  Valor unitario: ${int(precio_unitario):,}")
                lineas.append(f"  Subtotal: ${int(subtotal):,}")

            lineas.append("")

        lineas.append("━" * 12)
        lineas.append("")

    # Productos
    if productos:
        lineas.append("📦 PRODUCTOS")
        lineas.append("")

        for reserva_producto in productos:
            nombre = reserva_producto.producto.nombre
            cantidad = reserva_producto.cantidad

            # Usar precio congelado si existe, sino precio_base
            precio_unitario = (reserva_producto.precio_unitario_venta
                             if reserva_producto.precio_unitario_venta
                             else reserva_producto.producto.precio_base)
            subtotal = precio_unitario * cantidad

            lineas.append(f"• {nombre}")
            lineas.append(f"  Cantidad: {cantidad}")
            lineas.append(f"  Valor unitario: ${int(precio_unitario):,}")
            lineas.append(f"  Subtotal: ${int(subtotal):,}")
            lineas.append("")

        lineas.append("━" * 12)
        lineas.append("")

    # Gift Cards
    if giftcards:
        lineas.append("🎁 GIFT CARDS")
        lineas.append("")

        for giftcard in giftcards:
            destinatario = ""
            if giftcard.cliente_destinatario:
                destinatario = f"\n  Para: {giftcard.cliente_destinatario.nombre}"
            elif giftcard.destinatario_nombre:
                destinatario = f"\n  Para: {giftcard.destinatario_nombre}"

            lineas.append(f"• Gift Card ${int(giftcard.monto_inicial):,}{destinatario}")
            lineas.append("")

        lineas.append("━" * 12)
        lineas.append("")

    # Valor total con desglose
    total = reserva.total

    # Calcular totales por categoría usando precios congelados
    total_servicios = sum(
        ((rs.precio_unitario_venta if rs.precio_unitario_venta else rs.servicio.precio_base) *
         (rs.cantidad_personas or 1))
        for rs in servicios
    )
    total_productos = sum(
        ((rp.precio_unitario_venta if rp.precio_unitario_venta else rp.producto.precio_base) *
         rp.cantidad)
        for rp in productos
    )
    total_giftcards = sum(gc.monto_inicial for gc in giftcards)

    # Obtener descuentos aplicados
    descuentos = reserva.pagos.filter(metodo_pago='descuento')
    total_descuentos = sum(d.monto for d in descuentos)
    tiene_descuentos = total_descuentos > 0

    lineas.append("💰 RESUMEN DE VALORES")
    lineas.append("")

    # Mostrar desglose por tipo
    items_count = sum([1 if servicios else 0, 1 if productos else 0, 1 if giftcards else 0])

    if items_count > 1:
        if servicios:
            lineas.append(f"Servicios: ${int(total_servicios):,}")
        if productos:
            lineas.append(f"Productos: ${int(total_productos):,}")
        if giftcards:
            lineas.append(f"Gift Cards: ${int(total_giftcards):,}")
        lineas.append("")

    # Si hay descuentos, mostrar el desglose
    if tiene_descuentos:
        subtotal_sin_descuento = total_servicios + total_productos + total_giftcards
        lineas.append(f"Valor Normal: ${int(subtotal_sin_descuento):,}")
        lineas.append(f"Descuento: -${int(total_descuentos):,}")
        lineas.append(f"Valor con descuento: ${int(total):,}")
    else:
        lineas.append(f"VALOR TOTAL: ${int(total):,}")
    lineas.append("")
    lineas.append("━" * 12)
    lineas.append("")

    # Notas adicionales
    if reserva.comentarios and reserva.comentarios.strip():
        lineas.append("📝 NOTAS")
        lineas.append("")
        lineas.append(reserva.comentarios)
        lineas.append("")
        lineas.append("━" * 12)
        lineas.append("")

    # Despedida
    lineas.append("⏰ Esta cotización tiene validez hasta las 22:00 horas de hoy.")
    lineas.append("")
    lineas.append("⚠️ IMPORTANTE: Al no estar pagada la reserva, los servicios pueden ser agendados por otra persona a través de la web de Aremko.")
    lineas.append("")
    lineas.append("Para confirmar la reserva debes pagarla mediante transferencia bancaria. Los datos los puedes obtener por WhatsApp.")
    lineas.append("")
    lineas.append("¡Esperamos verte pronto en Aremko! 🌿✨")

    return '\n'.join(lineas)
