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

    # Buscar desayunos del día siguiente para preparar hoy
    manana = hoy + timedelta(days=1)

    # Solo buscar desayunos si la hora actual es antes de las 19:00
    desayunos_manana = []
    if hora_actual <= time(19, 0):
        desayunos_manana = ReservaServicio.objects.filter(
            fecha_agendamiento=manana,
            servicio__nombre__icontains='desayuno',
            venta_reserva__isnull=False
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).select_related(
            'servicio',
            'venta_reserva__cliente'
        ).order_by('hora_inicio')

    # Organizar por hora
    agenda_por_hora = defaultdict(list)

    for servicio in servicios_pendientes:
        hora_key = servicio.hora_inicio

        # Lógica inteligente para determinar dónde mostrar los productos
        productos_a_entregar = []

        # Obtener todos los servicios del día de esta reserva
        servicios_del_dia = ReservaServicio.objects.filter(
            venta_reserva=servicio.venta_reserva,
            fecha_agendamiento=hoy
        ).exclude(
            servicio__nombre__icontains='descuento'
        ).select_related('servicio').order_by('hora_inicio')

        # Identificar qué tipos de servicios hay en la reserva
        tiene_tina = any(s.servicio and s.servicio.tipo_servicio == 'tina' for s in servicios_del_dia)
        tiene_cabana = any(s.servicio and s.servicio.tipo_servicio == 'cabana' for s in servicios_del_dia)
        tiene_masaje = any(s.servicio and s.servicio.tipo_servicio == 'masaje' for s in servicios_del_dia)

        mostrar_productos_aqui = False

        # Determinar si este servicio debe mostrar los productos
        if tiene_tina:
            # Si hay tinas, mostrar productos con el primer servicio de tina
            primer_servicio_tina = servicios_del_dia.filter(servicio__tipo_servicio='tina').first()
            if primer_servicio_tina and primer_servicio_tina.id == servicio.id:
                mostrar_productos_aqui = True
        elif tiene_cabana:
            # Si no hay tinas pero hay cabañas, mostrar con la primera cabaña
            primer_servicio_cabana = servicios_del_dia.filter(servicio__tipo_servicio='cabana').first()
            if primer_servicio_cabana and primer_servicio_cabana.id == servicio.id:
                mostrar_productos_aqui = True
        elif tiene_masaje:
            # Solo si únicamente hay masajes, mostrar con el primer masaje
            primer_servicio_masaje = servicios_del_dia.filter(servicio__tipo_servicio='masaje').first()
            if primer_servicio_masaje and primer_servicio_masaje.id == servicio.id:
                mostrar_productos_aqui = True
        else:
            # Para otros tipos de servicio, mostrar con el primero
            primer_servicio = servicios_del_dia.first()
            if primer_servicio and primer_servicio.id == servicio.id:
                mostrar_productos_aqui = True

        # Solo procesar productos si este servicio debe mostrarlos
        if mostrar_productos_aqui:
            # Obtener productos de la reserva que NO sean descuentos
            productos = ReservaProducto.objects.filter(
                venta_reserva=servicio.venta_reserva
            ).select_related('producto')

            for producto in productos:
                # Verificar si el producto existe
                if not producto.producto:
                    continue

                # Verificar si es un descuento
                try:
                    nombre_producto = str(producto.producto.nombre or "").strip()
                    precio_producto = float(producto.producto.precio_base or 0)

                    es_descuento = any([
                        'descuento' in nombre_producto.lower(),
                        'discount' in nombre_producto.lower(),
                        'dto' in nombre_producto.lower(),
                        precio_producto < 0,
                        nombre_producto.startswith('-'),
                    ])

                    # Si NO es descuento, añadirlo a la lista para mostrar
                    if not es_descuento:
                        productos_a_entregar.append(producto)
                except Exception:
                    # En caso de error, no incluir el producto
                    continue

        # Agregar a la agenda (con verificaciones de seguridad)
        if servicio.servicio and servicio.venta_reserva and servicio.venta_reserva.cliente:
            # Obtener estado de pago y montos
            venta = servicio.venta_reserva
            estado_pago = venta.estado_pago
            total = venta.total
            pagado = venta.pagado
            saldo_pendiente = venta.saldo_pendiente

            agenda_por_hora[hora_key].append({
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
                'duracion': servicio.servicio.duracion if servicio.servicio else None,  # Duración en minutos
                'estado_pago': estado_pago,
                'total': total,
                'pagado': pagado,
                'saldo_pendiente': saldo_pendiente
            })

    # Agregar desayunos del día siguiente si los hay
    if desayunos_manana:
        # Agrupar desayunos por preparación
        desayunos_info = []
        for desayuno in desayunos_manana:
            if desayuno.servicio and desayuno.venta_reserva and desayuno.venta_reserva.cliente:
                desayunos_info.append({
                    'cliente': desayuno.venta_reserva.cliente.nombre,
                    'hora_servicio': desayuno.hora_inicio,
                    'cantidad_personas': desayuno.cantidad_personas or 1,
                    'reserva_id': desayuno.venta_reserva.id,
                    'estado_pago': desayuno.venta_reserva.estado_pago
                })

        # Agregar bloque de preparación de desayunos a las 19:00
        agenda_por_hora['19:00'].append({
            'tipo': 'preparacion_desayuno',
            'nombre': f'Preparación de Desayunos - {len(desayunos_info)} servicio(s) para mañana',
            'cliente': 'Múltiples clientes',
            'es_preparacion': True,
            'cantidad_desayunos': len(desayunos_info),
            'desayunos_detalle': desayunos_info,
            'es_proximo': False,
            'en_curso': False,
            'hora_fin': '22:00',
            'duracion': 180,  # 3 horas
            'estado_pago': 'preparacion',  # Estado especial
            'total': 0,
            'pagado': 0,
            'saldo_pendiente': 0
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
    total_servicios = sum(len(h['items']) for h in agenda_ordenada) if agenda_ordenada else 0
    # Sumar las CANTIDADES de productos, no solo contar los ítems
    total_productos = sum(
        producto.cantidad
        for h in agenda_ordenada
        for item in h.get('items', [])
        for producto in item.get('productos', [])
    ) if agenda_ordenada else 0
    # Contar servicios en curso
    servicios_en_curso = sum(
        1 for h in agenda_ordenada
        for item in h.get('items', [])
        if item.get('en_curso', False)
    ) if agenda_ordenada else 0

    # Contar servicios por estado de pago
    servicios_pagados = sum(
        1 for h in agenda_ordenada
        for item in h.get('items', [])
        if item.get('estado_pago') == 'pagado'
    ) if agenda_ordenada else 0

    servicios_parcial = sum(
        1 for h in agenda_ordenada
        for item in h.get('items', [])
        if item.get('estado_pago') == 'parcial'
    ) if agenda_ordenada else 0

    servicios_pendientes_pago = sum(
        1 for h in agenda_ordenada
        for item in h.get('items', [])
        if item.get('estado_pago') == 'pendiente'
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
                        precio = float(prod.producto.precio_base or 0)
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
        'servicios_pagados': servicios_pagados,
        'servicios_parcial': servicios_parcial,
        'servicios_pendientes_pago': servicios_pendientes_pago,
        'tiene_tareas': len(agenda_ordenada) > 0,
        'debug_mode': debug_mode,
        'debug_info': debug_info
    }

    return render(request, 'ventas/agenda_operativa.html', context)