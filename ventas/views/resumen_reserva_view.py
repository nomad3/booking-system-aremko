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
    tiene_alojamiento = any(s.servicio.tipo_servicio == 'cabana' for s in servicios)
    tiene_tinas = any(s.servicio.tipo_servicio == 'tina' for s in servicios)
    tiene_masajes = any(s.servicio.tipo_servicio == 'masaje' for s in servicios)

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
        detalle_servicio = f"{nombre} ({personas} persona{'s' if personas > 1 else ''}) - {fecha}{hora_texto}"
        lineas.append(detalle_servicio)

        # Agregar información adicional del servicio si existe
        if servicio_reserva.servicio.informacion_adicional:
            lineas.append(f"  {servicio_reserva.servicio.informacion_adicional}")

    lineas.append("")
    lineas.append("")

    # Agregar texto de Tina Yate si hay tinas
    if tiene_tinas:
        lineas.append(config.tina_yate_texto)
        lineas.append("")
        lineas.append("")

    # Valor total
    total = reserva.total
    lineas.append(f"VALOR TOTAL: ${int(total):,}")

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
        lineas.append("")
        lineas.append(config.seguridad_pasarela)
    else:
        lineas.append("Detalles Adicionales:")
        lineas.append(config.cortesias_generales)
        lineas.append(config.seguridad_pasarela)

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
