"""
Vista para generar resúmenes de reserva (pre-pago)
"""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from datetime import datetime
from ..models import VentaReserva, ConfiguracionResumen


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def generar_resumen_prepago(request, reserva_id):
    """
    Vista para generar el resumen de reserva pre-pago.
    Muestra el texto generado en un textarea editable para copiar/enviar.
    """
    reserva = get_object_or_404(VentaReserva, id=reserva_id)
    config = ConfiguracionResumen.get_solo()

    # Generar el texto del resumen
    texto_resumen = _generar_texto_resumen(reserva, config)

    context = {
        'reserva': reserva,
        'texto_resumen': texto_resumen,
        'config': config,
    }

    return render(request, 'ventas/resumen_prepago.html', context)


def _generar_texto_resumen(reserva, config):
    """
    Genera el texto del resumen de reserva según los servicios contratados.

    Args:
        reserva: Instancia de VentaReserva
        config: Instancia de ConfiguracionResumen

    Returns:
        str: Texto del resumen formateado
    """
    lineas = []

    # Encabezado
    lineas.append(f"{config.encabezado} 🌿✨")
    lineas.append("")

    # Número de reserva
    lineas.append(f"Reserva Nº {reserva.id}")
    lineas.append("")

    # Detectar tipo de reserva
    servicios = reserva.reservaservicios.all().select_related('servicio', 'servicio__categoria')
    productos = reserva.reservaproductos.all().select_related('producto')
    giftcards = reserva.giftcards.all()

    # Lista de cabañas reales (alojamiento verdadero)
    CABANAS_REALES = ['torre', 'acantilado', 'laurel', 'tepa', 'arrayan']

    tiene_alojamiento = any(
        s.servicio.tipo_servicio == 'cabana' and
        any(cabana in s.servicio.nombre.lower() for cabana in CABANAS_REALES)
        for s in servicios
    )
    tiene_tinas = any(s.servicio.tipo_servicio == 'tina' for s in servicios)
    tiene_masajes = any(s.servicio.tipo_servicio == 'masaje' for s in servicios)

    # Servicios contratados
    if servicios:
        lineas.append("Servicios contratados:")
        lineas.append("")

        # Listar TODOS los servicios con fecha, hora y personas
        servicios_ordenados = sorted(servicios, key=lambda s: (s.fecha_agendamiento, s.hora_inicio or ''))

        for servicio_reserva in servicios_ordenados:
            nombre = servicio_reserva.servicio.nombre
            personas = servicio_reserva.cantidad_personas or 1
            fecha = servicio_reserva.fecha_agendamiento.strftime('%d/%m/%Y')

            # Formatear hora
            hora_texto = ""
            if servicio_reserva.hora_inicio:
                hora_texto = f" - {servicio_reserva.hora_inicio} hrs"

            # Formato: Nombre del servicio (X personas) - DD/MM/YYYY - HH:MM hrs
            # No mostrar personas para Desayuno
            if 'desayuno' in nombre.lower():
                detalle_servicio = f"{nombre} - {fecha}{hora_texto}"
            else:
                detalle_servicio = f"{nombre} ({personas} persona{'s' if personas > 1 else ''}) - {fecha}{hora_texto}"
            lineas.append(detalle_servicio)

            # Agregar información adicional del servicio si existe
            if servicio_reserva.servicio.informacion_adicional:
                lineas.append(f"  {servicio_reserva.servicio.informacion_adicional}")

        lineas.append("")

    # Productos
    if productos:
        lineas.append("Productos:")
        lineas.append("")
        for reserva_producto in productos:
            lineas.append(f"{reserva_producto.producto.nombre} (x{reserva_producto.cantidad})")
        lineas.append("")

    # Gift Cards
    if giftcards:
        lineas.append("Gift Cards incluidas:")
        lineas.append("")
        for giftcard in giftcards:
            destinatario = ""
            if giftcard.cliente_destinatario:
                destinatario = f" - Para: {giftcard.cliente_destinatario.nombre}"
            elif giftcard.destinatario_nombre:
                destinatario = f" - Para: {giftcard.destinatario_nombre}"

            lineas.append(f"Gift Card ${int(giftcard.monto_inicial):,}{destinatario}")
        lineas.append("")

    # Comentarios (información específica de la reserva)
    if reserva.comentarios and reserva.comentarios.strip():
        lineas.append("Notas importantes:")
        lineas.append(reserva.comentarios)
        lineas.append("")

    lineas.append("")

    # Agregar texto de Tina Yate si hay tinas
    if tiene_tinas:
        lineas.append(config.tina_yate_texto)
        lineas.append("")
        lineas.append("")

    # Valor total con desglose
    total = reserva.total
    total_servicios = sum(rs.servicio.precio_base * (rs.cantidad_personas or 1) for rs in servicios)
    total_productos = sum(rp.producto.precio_base * rp.cantidad for rp in productos)
    total_giftcards = sum(gc.monto_inicial for gc in giftcards)

    lineas.append(f"VALOR TOTAL: ${int(total):,}")

    # Mostrar desglose solo si hay más de un tipo de item
    items_count = sum([1 if servicios else 0, 1 if productos else 0, 1 if giftcards else 0])
    if items_count > 1:
        if servicios:
            lineas.append(f"  - Servicios: ${int(total_servicios):,}")
        if productos:
            lineas.append(f"  - Productos: ${int(total_productos):,}")
        if giftcards:
            lineas.append(f"  - Gift Cards: ${int(total_giftcards):,}")

    lineas.append("")
    lineas.append("")

    # Políticas de cancelación
    lineas.append("Condiciones de Reserva Anular o Cambiar Reserva :")
    if tiene_alojamiento:
        lineas.append(config.politica_alojamiento)
    if tiene_tinas or tiene_masajes:
        lineas.append(config.politica_tinas_masajes)

    lineas.append("")

    # Información adicional
    if tiene_alojamiento:
        lineas.append("Información Adicional")
        lineas.append(config.equipamiento_cabanas)
        lineas.append("")
        lineas.append(config.cortesias_alojamiento)
    else:
        lineas.append("Detalles Adicionales:")
        lineas.append(config.cortesias_generales)

    lineas.append("")

    # Despedida
    lineas.append(config.despedida)

    lineas.append("")
    lineas.append("")

    # Datos de pago
    lineas.append(config.datos_transferencia)
    lineas.append("")
    lineas.append(f"{config.texto_link_pago} {config.link_pago_mercadopago}")

    return '\n'.join(lineas)
