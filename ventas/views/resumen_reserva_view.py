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

    # Detectar tipo de reserva
    servicios = reserva.reservaservicio_set.all().select_related('servicio', 'servicio__categoria')
    tiene_alojamiento = any(s.servicio.tipo_servicio == 'cabana' for s in servicios)
    tiene_tinas = any(s.servicio.tipo_servicio == 'tina' for s in servicios)
    tiene_masajes = any(s.servicio.tipo_servicio == 'masaje' for s in servicios)

    # Determinar título del programa
    if tiene_alojamiento:
        # Obtener el nombre de la cabaña principal
        servicio_cabana = next((s for s in servicios if s.servicio.tipo_servicio == 'cabana'), None)
        if servicio_cabana:
            titulo_programa = f"Programa {servicio_cabana.servicio.nombre}"
        else:
            titulo_programa = "Programa Alojamiento"
    elif tiene_tinas and tiene_masajes:
        titulo_programa = "Resumen de su programa en Aremko Spa"
    else:
        titulo_programa = "Confirmación"

    lineas.append(titulo_programa)

    # Número de reserva y fecha
    fecha_reserva = reserva.fecha_creacion.strftime('%d/%m/%Y') if reserva.fecha_creacion else datetime.now().strftime('%d/%m/%Y')
    lineas.append(f"Reserva Nº {reserva.id}")

    # Si es alojamiento, mostrar check-in/check-out
    if tiene_alojamiento:
        servicios_alojamiento = [s for s in servicios if s.servicio.tipo_servicio == 'cabana']
        if servicios_alojamiento:
            primer_servicio = min(servicios_alojamiento, key=lambda s: s.fecha_agendamiento)
            # Calcular check-out (asumiendo 1 noche, ajustar según duración)
            fecha_checkout = primer_servicio.fecha_agendamiento
            # Buscar si hay más de un día de alojamiento
            dias_alojamiento = len(set(s.fecha_agendamiento for s in servicios_alojamiento))

            lineas.append(f"Check in desde las 16:00hrs. {primer_servicio.fecha_agendamiento.strftime('%d/%m/%Y')}")
            # Simplificado: asumiendo checkout al día siguiente
            from datetime import timedelta
            fecha_checkout = primer_servicio.fecha_agendamiento + timedelta(days=1)
            lineas.append(f"Check out 11:00 hrs {fecha_checkout.strftime('%d/%m/%Y')}")

    lineas.append("Incluye:")

    # Listar servicios agrupados
    if tiene_alojamiento:
        lineas.append(f"Alojamiento: {len([s for s in servicios if s.servicio.tipo_servicio == 'cabana'])} noche(s)")

    # Listar otros servicios con horarios
    servicios_ordenados = sorted(servicios, key=lambda s: (s.fecha_agendamiento, s.hora_inicio or ''))

    for servicio_reserva in servicios_ordenados:
        if servicio_reserva.servicio.tipo_servicio == 'cabana':
            continue  # Ya lo listamos arriba

        nombre = servicio_reserva.servicio.nombre
        personas = servicio_reserva.cantidad_personas or 1

        # Formatear hora
        hora_texto = ""
        if servicio_reserva.hora_inicio:
            hora_texto = f"{servicio_reserva.hora_inicio} hrs"

        # Formatear fecha si es diferente
        fecha_texto = ""
        if not tiene_alojamiento or servicio_reserva.fecha_agendamiento != primer_servicio.fecha_agendamiento:
            fecha_texto = f" - {servicio_reserva.fecha_agendamiento.strftime('%d/%m/%Y')}"

        lineas.append(f"{nombre}")
        if hora_texto:
            lineas.append(hora_texto)

        # Agregar información adicional del servicio si existe
        if servicio_reserva.servicio.informacion_adicional:
            lineas.append(servicio_reserva.servicio.informacion_adicional)

    lineas.append("")
    lineas.append("")

    # Agregar texto de Tina Yate si hay tinas
    if tiene_tinas:
        lineas.append(config.tina_yate_texto)
        lineas.append("")

    # Agregar sauna no disponible si hay alojamiento
    if tiene_alojamiento:
        lineas.append(config.sauna_no_disponible)
        lineas.append("")
        lineas.append("")

    # Valor total
    total = reserva.total
    if tiene_tinas and tiene_masajes and not tiene_alojamiento:
        lineas.append(f"Valor programa de domingo a jueves ${int(total):,} (pago total al confirmar)")
    else:
        personas_texto = ""
        # Contar personas totales
        total_personas = sum(s.cantidad_personas or 1 for s in servicios if s.servicio.tipo_servicio != 'cabana')
        if total_personas > 0:
            personas_texto = f" - {total_personas} adulto{'s' if total_personas > 1 else ''}"

        lineas.append(f"Valor ${int(total):,}{personas_texto}")

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
