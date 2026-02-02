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

    # Modo debug para ver todos los servicios del día
    debug_mode = request.GET.get('debug', '').lower() == 'true'
    if debug_mode:
        hora_actual = time(0, 0)  # Mostrar desde las 00:00 en modo debug

    # Obtener todos los servicios del día desde la hora actual
    # Primero filtrar servicios que tienen venta_reserva asociada
    # Excluir servicios de descuento que no son servicios reales
    servicios = ReservaServicio.objects.filter(
        fecha_agendamiento=hoy,
        venta_reserva__isnull=False  # Asegurar que hay venta_reserva
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).exclude(
        servicio__nombre__icontains='descuento'  # Excluir servicios de descuento
    ).select_related(
        'servicio',
        'venta_reserva__cliente'
    ).order_by('hora_inicio')

    # Filtrar servicios desde la hora actual en adelante Y servicios en curso
    servicios_pendientes = []
    for servicio in servicios:
        try:
            # Validar que hora_inicio existe y tiene formato correcto
            if not servicio.hora_inicio:
                continue

            servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()

            # Calcular hora de fin basado en la duración del servicio
            if servicio.servicio and hasattr(servicio.servicio, 'duracion') and servicio.servicio.duracion:
                hora_inicio_dt = datetime.combine(hoy, servicio_hora)
                hora_fin_dt = hora_inicio_dt + timedelta(minutes=int(servicio.servicio.duracion))
                hora_fin = hora_fin_dt.time()

                # Incluir si:
                # 1. El servicio aún no ha comenzado (futuro)
                # 2. El servicio está en curso (ya comenzó pero no ha terminado)
                if servicio_hora >= hora_actual or (servicio_hora < hora_actual and hora_fin > hora_actual):
                    # Marcar si está en curso
                    servicio.en_curso = (servicio_hora < hora_actual and hora_fin > hora_actual)
                    servicio.hora_fin = hora_fin.strftime('%H:%M')
                    servicios_pendientes.append(servicio)
            else:
                # Si no hay duración, usar lógica anterior (solo futuros)
                if servicio_hora >= hora_actual:
                    servicio.en_curso = False
                    servicio.hora_fin = None
                    servicios_pendientes.append(servicio)
        except Exception as e:
            # Log del error pero continuar con otros servicios
            continue

    # Organizar por hora
    agenda_por_hora = defaultdict(list)

    for servicio in servicios_pendientes:
        hora_key = servicio.hora_inicio

        # Obtener productos asociados a esta reserva (excluyendo descuentos)
        productos = ReservaProducto.objects.filter(
            venta_reserva=servicio.venta_reserva
        ).select_related('producto')

        # Determinar si los productos se entregan con este servicio
        productos_a_entregar = []
        productos_debug = [] if debug_mode else None

        for producto in productos:
            # Debug: registrar todos los productos procesados
            if debug_mode and producto.producto:
                productos_debug.append({
                    'nombre': producto.producto.nombre,
                    'fecha_entrega': producto.fecha_entrega,
                    'cantidad': producto.cantidad,
                    'precio': producto.producto.precio
                })

            # Verificar si el producto existe
            if not producto.producto:
                continue

            # Verificar si es un descuento PRIMERO
            try:
                nombre_producto = str(producto.producto.nombre or "").strip()
                precio_producto = float(producto.producto.precio or 0)

                # Más exhaustivo: verificar múltiples condiciones de descuento
                es_descuento = any([
                    'descuento' in nombre_producto.lower(),
                    'discount' in nombre_producto.lower(),
                    'dto' in nombre_producto.lower(),
                    precio_producto < 0,
                    nombre_producto.startswith('-'),
                    # Específicamente para casos como "Descuento -500"
                    nombre_producto.lower().startswith('descuento -'),
                    nombre_producto.lower().startswith('descuento-'),
                ])

                if es_descuento:
                    continue  # Saltar productos de descuento
            except Exception:
                continue  # Si hay error, saltar este producto

            # Ahora verificar si el producto se debe entregar con este servicio
            entregar_con_este_servicio = False

            # Comparar fechas correctamente (date vs datetime)
            if producto.fecha_entrega:
                # Si fecha_entrega es datetime, convertir a date para comparar
                fecha_entrega_date = producto.fecha_entrega
                if hasattr(producto.fecha_entrega, 'date'):
                    fecha_entrega_date = producto.fecha_entrega.date()

                if fecha_entrega_date == hoy:
                    # Si tiene fecha de entrega explícita de hoy, se entrega
                    entregar_con_este_servicio = True
            else:
                # Si no tiene fecha de entrega, verificar si este es el primer servicio del día
                primer_servicio = ReservaServicio.objects.filter(
                    venta_reserva=servicio.venta_reserva,
                    fecha_agendamiento=hoy
                ).exclude(
                    servicio__nombre__icontains='descuento'
                ).order_by('hora_inicio').first()

                if primer_servicio and primer_servicio.id == servicio.id:
                    entregar_con_este_servicio = True

            if entregar_con_este_servicio:
                productos_a_entregar.append(producto)

        # Agregar a la agenda (con verificaciones de seguridad)
        if servicio.servicio and servicio.venta_reserva and servicio.venta_reserva.cliente:
            item_agenda = {
                'servicio': servicio,
                'tipo': 'servicio',
                'nombre': servicio.servicio.nombre,
                'cliente': servicio.venta_reserva.cliente.nombre,
                'reserva_id': servicio.venta_reserva.id,
                'cantidad_personas': servicio.cantidad_personas or 1,
                'productos': productos_a_entregar,
                'es_proximo': False,  # Se marcará después
                'en_curso': getattr(servicio, 'en_curso', False),  # Si está en ejecución
                'hora_fin': getattr(servicio, 'hora_fin', None),  # Hora de finalización
                'duracion': servicio.servicio.duracion if servicio.servicio else None  # Duración en minutos
            }

            # Debug específico para reserva #4718
            if debug_mode and servicio.venta_reserva.id == 4718:
                item_agenda['debug_productos'] = productos_debug
                item_agenda['debug_info'] = {
                    'total_productos_reserva': len(productos_debug) if productos_debug else 0,
                    'productos_a_entregar': len(productos_a_entregar),
                    'fecha_hoy': str(hoy)
                }

            agenda_por_hora[hora_key].append(item_agenda)

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
    total_servicios = sum(len(h['items']) for h in agenda_ordenada) if agenda_ordenada else 0
    total_productos = sum(
        len(item.get('productos', []))
        for h in agenda_ordenada
        for item in h.get('items', [])
    ) if agenda_ordenada else 0
    # Contar servicios en curso
    servicios_en_curso = sum(
        1 for h in agenda_ordenada
        for item in h.get('items', [])
        if item.get('en_curso', False)
    ) if agenda_ordenada else 0

    # Identificar próximos servicios (próxima hora)
    if agenda_ordenada:
        primera_hora = agenda_ordenada[0]['hora']
        for item in agenda_ordenada[0]['items']:
            item['es_proximo'] = True

    # En modo debug, agregar información adicional
    debug_info = None
    if debug_mode:
        # Contar todos los servicios antes de filtrar (excluyendo descuentos)
        todos_servicios = ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).count()

        # Servicios por estado (excluyendo descuentos)
        servicios_por_estado = {}
        for servicio in ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('venta_reserva', 'servicio'):
            if servicio.servicio:  # Verificar que el servicio existe
                estado = servicio.venta_reserva.estado_reserva if servicio.venta_reserva else 'sin_reserva'
                servicios_por_estado[estado] = servicios_por_estado.get(estado, 0) + 1

        # Mostrar algunos servicios de ejemplo (excluyendo descuentos)
        primeros_servicios = []
        for servicio in ReservaServicio.objects.filter(
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('servicio', 'venta_reserva__cliente')[:5]:
            if servicio.servicio:  # Verificar que el servicio existe
                primeros_servicios.append({
                    'id': servicio.id,
                    'servicio': servicio.servicio.nombre,
                    'hora': servicio.hora_inicio,
                    'cliente': servicio.venta_reserva.cliente.nombre if servicio.venta_reserva and servicio.venta_reserva.cliente else 'Sin cliente',
                    'estado': servicio.venta_reserva.estado_reserva if servicio.venta_reserva else 'Sin reserva'
                })

        # Contar productos filtrados como descuento
        productos_descuento_filtrados = []
        total_productos_filtrados = 0
        for venta in VentaReserva.objects.filter(fecha_venta=hoy):
            for prod in ReservaProducto.objects.filter(venta_reserva=venta).select_related('producto'):
                if prod.producto:
                    try:
                        nombre = str(prod.producto.nombre or "").strip()
                        precio = float(prod.producto.precio or 0)
                        if 'descuento' in nombre.lower() or precio < 0:
                            total_productos_filtrados += 1
                            if len(productos_descuento_filtrados) < 5:  # Solo mostrar primeros 5
                                productos_descuento_filtrados.append({
                                    'nombre': nombre,
                                    'precio': precio
                                })
                    except:
                        pass

        debug_info = {
            'total_servicios_hoy': todos_servicios,
            'servicios_filtrados': len(servicios),
            'servicios_pendientes': len(servicios_pendientes),
            'servicios_en_curso': servicios_en_curso,
            'servicios_por_estado': servicios_por_estado,
            'primeros_servicios': primeros_servicios,
            'productos_descuento_filtrados': productos_descuento_filtrados,
            'total_productos_descuento': total_productos_filtrados,
            'hora_actual_str': hora_actual.strftime('%H:%M'),
            'fecha_hoy': hoy.strftime('%Y-%m-%d')
        }

    context = {
        'agenda': agenda_ordenada,
        'fecha_actual': hoy.strftime('%d/%m/%Y'),
        'hora_actual': hora_actual.strftime('%H:%M'),
        'hora_generacion': ahora.strftime('%H:%M'),
        'total_servicios': total_servicios,
        'servicios_en_curso': servicios_en_curso,
        'total_productos': total_productos,
        'tiene_tareas': len(agenda_ordenada) > 0,
        'debug_mode': debug_mode,
        'debug_info': debug_info
    }

    return render(request, 'ventas/agenda_operativa.html', context)