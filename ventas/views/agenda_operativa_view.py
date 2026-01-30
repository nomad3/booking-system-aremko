"""
Vista para mostrar la agenda operativa del día con servicios y productos
organizados cronológicamente desde la hora actual en adelante.
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Q, Min
from django.utils import timezone
from datetime import datetime, time, timedelta
from collections import defaultdict
from ..models import ReservaServicio, ReservaProducto, VentaReserva

def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)

@staff_required
def agenda_operativa(request):
    """
    Vista principal de la agenda operativa del día.
    Muestra todos los servicios y productos pendientes desde la hora actual,
    organizados cronológicamente.
    """
    # Obtener fecha y hora actuales en zona horaria local
    ahora = timezone.localtime(timezone.now())
    hoy = ahora.date()
    hora_actual = ahora.time()

    # Si se especifica una hora de inicio (para testing), usarla
    hora_inicio_param = request.GET.get('desde_hora')
    if hora_inicio_param:
        try:
            hora_actual = datetime.strptime(hora_inicio_param, '%H:%M').time()
        except:
            pass  # Usar hora actual si hay error

    # Obtener todos los servicios del día desde la hora actual
    servicios = ReservaServicio.objects.filter(
        fecha_agendamiento=hoy,
        venta_reserva__estado_reserva__in=['confirmada', 'en_proceso']
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).select_related(
        'servicio',
        'venta_reserva__cliente'
    ).order_by('hora_inicio')

    # Filtrar servicios desde la hora actual en adelante
    servicios_pendientes = []
    for servicio in servicios:
        try:
            servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()
            if servicio_hora >= hora_actual:
                servicios_pendientes.append(servicio)
        except:
            continue

    # Organizar por hora
    agenda_por_hora = defaultdict(list)

    for servicio in servicios_pendientes:
        hora_key = servicio.hora_inicio

        # Obtener productos asociados a esta reserva
        productos = ReservaProducto.objects.filter(
            venta_reserva=servicio.venta_reserva
        ).select_related('producto')

        # Determinar si los productos se entregan con este servicio
        productos_a_entregar = []
        for producto in productos:
            entregar_con_este_servicio = False

            if producto.fecha_entrega == hoy:
                # Si tiene fecha de entrega explícita de hoy, se entrega
                entregar_con_este_servicio = True
            elif producto.fecha_entrega is None:
                # Si no tiene fecha, verificar si este es el primer servicio
                primer_servicio = ReservaServicio.objects.filter(
                    venta_reserva=servicio.venta_reserva,
                    fecha_agendamiento=hoy
                ).order_by('hora_inicio').first()

                if primer_servicio and primer_servicio.id == servicio.id:
                    entregar_con_este_servicio = True

            if entregar_con_este_servicio:
                productos_a_entregar.append(producto)

        # Agregar a la agenda
        agenda_por_hora[hora_key].append({
            'servicio': servicio,
            'tipo': 'servicio',
            'nombre': servicio.servicio.nombre,
            'cliente': servicio.venta_reserva.cliente.nombre,
            'reserva_id': servicio.venta_reserva.id,
            'cantidad_personas': servicio.cantidad_personas or 1,
            'productos': productos_a_entregar,
            'es_proximo': False  # Se marcará después
        })

    # Convertir a lista ordenada y marcar servicios urgentes
    agenda_ordenada = []
    hora_limite_urgente = (ahora + timedelta(minutes=30)).time()

    for hora in sorted(agenda_por_hora.keys()):
        hora_obj = datetime.strptime(hora, '%H:%M').time()
        es_urgente = hora_obj <= hora_limite_urgente

        agenda_ordenada.append({
            'hora': hora,
            'es_urgente': es_urgente,
            'items': agenda_por_hora[hora]
        })

    # Calcular estadísticas
    total_servicios = sum(len(h['items']) for h in agenda_ordenada)
    total_productos = sum(
        len(item['productos'])
        for h in agenda_ordenada
        for item in h['items']
    )

    # Identificar próximos servicios (próxima hora)
    if agenda_ordenada:
        primera_hora = agenda_ordenada[0]['hora']
        for item in agenda_ordenada[0]['items']:
            item['es_proximo'] = True

    context = {
        'agenda': agenda_ordenada,
        'fecha_actual': hoy.strftime('%d/%m/%Y'),
        'hora_actual': hora_actual.strftime('%H:%M'),
        'hora_generacion': ahora.strftime('%H:%M'),
        'total_servicios': total_servicios,
        'total_productos': total_productos,
        'tiene_tareas': len(agenda_ordenada) > 0
    }

    return render(request, 'ventas/agenda_operativa.html', context)