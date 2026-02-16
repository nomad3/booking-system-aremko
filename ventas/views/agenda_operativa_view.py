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

    # Filtro de vista: actual (desde hora actual), todos (todo el día), pasados (anteriores a hora actual), pendientes_pago
    filtro_vista = request.GET.get('filtro', 'actual')
    if filtro_vista not in ['actual', 'todos', 'pasados', 'pendientes_pago']:
        filtro_vista = 'actual'  # Default seguro

    # Aplicar filtro
    hora_filtro_inicio = hora_actual
    hora_filtro_fin = time(23, 59)

    if filtro_vista == 'todos':
        hora_filtro_inicio = time(0, 0)  # Desde las 00:00
        hora_filtro_fin = time(23, 59)
    elif filtro_vista == 'pasados':
        hora_filtro_inicio = time(0, 0)
        hora_filtro_fin = hora_actual  # Hasta la hora actual
    elif filtro_vista == 'pendientes_pago':
        hora_filtro_inicio = time(0, 0)  # Todo el día
        hora_filtro_fin = time(23, 59)

    # Determinar rango de fechas según filtro
    if filtro_vista == 'pendientes_pago':
        # Incluir día actual y día anterior (para cabañas con alojamiento)
        ayer = hoy - timedelta(days=1)
        fecha_filtro = Q(fecha_agendamiento=hoy) | Q(fecha_agendamiento=ayer)
    else:
        # Solo día actual
        fecha_filtro = Q(fecha_agendamiento=hoy)

    # Obtener servicios según filtro de fecha
    # Primero filtrar servicios que tienen venta_reserva asociada
    # Excluir servicios de descuento que no son servicios reales
    servicios = ReservaServicio.objects.filter(
        fecha_filtro,
        venta_reserva__isnull=False  # Asegurar que hay venta_reserva
    ).exclude(
        venta_reserva__estado_reserva='cancelada'
    ).exclude(
        servicio__nombre__icontains='descuento'  # Excluir servicios de descuento
    ).select_related(
        'servicio',
        'venta_reserva__cliente'
    ).order_by('fecha_agendamiento', 'hora_inicio')

    # Filtrar servicios según el filtro seleccionado
    servicios_pendientes = []
    for servicio in servicios:
        try:
            # Validar que hora_inicio existe y tiene formato correcto
            if not servicio.hora_inicio:
                continue

            # Para filtro de pendientes_pago, verificar estado de pago primero
            if filtro_vista == 'pendientes_pago':
                estado_pago = servicio.venta_reserva.estado_pago if servicio.venta_reserva else None
                if estado_pago not in ['pendiente', 'parcial']:
                    continue  # Saltar servicios pagados o sin estado

            # Determinar fecha del servicio para cálculos de hora
            fecha_servicio = servicio.fecha_agendamiento
            servicio_hora = datetime.strptime(servicio.hora_inicio, '%H:%M').time()

            # Calcular hora de fin basado en la duración del servicio
            if servicio.servicio and hasattr(servicio.servicio, 'duracion') and servicio.servicio.duracion:
                hora_inicio_dt = datetime.combine(fecha_servicio, servicio_hora)
                hora_fin_dt = hora_inicio_dt + timedelta(minutes=int(servicio.servicio.duracion))
                hora_fin = hora_fin_dt.time()

                # Marcar si está en curso o ya pasó (solo relevante para día actual)
                if fecha_servicio == hoy:
                    en_curso = (servicio_hora < hora_actual and hora_fin > hora_actual)
                    es_pasado = (hora_fin <= hora_actual)
                else:
                    # Servicios de ayer siempre son pasados
                    en_curso = False
                    es_pasado = True

                servicio.en_curso = en_curso
                servicio.es_pasado = es_pasado
                servicio.hora_fin = hora_fin.strftime('%H:%M')

                # Aplicar filtro según vista seleccionada
                if filtro_vista == 'pendientes_pago':
                    # Ya filtrado por estado_pago arriba, incluir todos
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'todos':
                    # Mostrar todos los servicios del día
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'pasados':
                    # Mostrar solo servicios que ya terminaron
                    if fecha_servicio == hoy and hora_fin <= hora_actual:
                        servicios_pendientes.append(servicio)
                    elif fecha_servicio < hoy:
                        servicios_pendientes.append(servicio)
                else:  # filtro_vista == 'actual'
                    # Mostrar servicios futuros o en curso (comportamiento original)
                    if fecha_servicio == hoy and (servicio_hora >= hora_actual or en_curso):
                        servicios_pendientes.append(servicio)
            else:
                # Si no hay duración, usar lógica simplificada
                if fecha_servicio == hoy:
                    servicio.en_curso = False
                    servicio.es_pasado = (servicio_hora < hora_actual)
                else:
                    servicio.en_curso = False
                    servicio.es_pasado = True
                servicio.hora_fin = None

                if filtro_vista == 'pendientes_pago':
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'todos':
                    servicios_pendientes.append(servicio)
                elif filtro_vista == 'pasados':
                    if fecha_servicio < hoy or (fecha_servicio == hoy and servicio_hora < hora_actual):
                        servicios_pendientes.append(servicio)
                else:  # filtro_vista == 'actual'
                    if fecha_servicio == hoy and servicio_hora >= hora_actual:
                        servicios_pendientes.append(servicio)
        except Exception as e:
            # Log del error pero continuar con otros servicios
            continue

    # Buscar desayunos del día siguiente para preparar hoy
    manana = hoy + timedelta(days=1)

    # Solo buscar desayunos si la hora actual es antes de las 23:00
    desayunos_manana = []
    if hora_actual <= time(23, 0):
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

    # Organizar por hora (y opcionalmente por fecha si es filtro de pagos pendientes)
    if filtro_vista == 'pendientes_pago':
        # Para pagos pendientes, organizar primero por fecha, luego por hora
        agenda_por_fecha = defaultdict(lambda: defaultdict(list))
    else:
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
            # Verificar si la reserva tiene un servicio de desayuno hoy
            tiene_desayuno_hoy = servicios_del_dia.filter(
                servicio__nombre__icontains='desayuno'
            ).exists()

            # Determinar si el servicio actual es de desayuno
            es_servicio_desayuno = servicio.servicio and 'desayuno' in servicio.servicio.nombre.lower()

            # Obtener productos de la reserva que NO sean descuentos
            # y que no hayan sido entregados en días anteriores
            productos = ReservaProducto.objects.filter(
                venta_reserva=servicio.venta_reserva
            ).filter(
                # Incluir solo productos con fecha_entrega de hoy o sin fecha_entrega (NULL)
                Q(fecha_entrega__isnull=True) | Q(fecha_entrega=hoy)
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

                    # Si NO es descuento, verificar si debe mostrarse
                    if not es_descuento:
                        # Si es un producto de desayuno (café, etc.)
                        es_producto_desayuno = any([
                            'cafe' in nombre_producto.lower(),
                            'café' in nombre_producto.lower(),
                            'desayuno' in nombre_producto.lower(),
                            'marley' in nombre_producto.lower(),  # Café Marley
                            'jugo' in nombre_producto.lower(),
                            'leche' in nombre_producto.lower(),
                            'pan' in nombre_producto.lower(),
                            'mantequilla' in nombre_producto.lower(),
                            'mermelada' in nombre_producto.lower()
                        ])

                        # Lógica especial para productos de desayuno
                        if es_producto_desayuno and tiene_desayuno_hoy and not es_servicio_desayuno:
                            # Si hay desayuno hoy y el servicio actual NO es desayuno,
                            # NO mostrar productos de desayuno (ya se entregaron en la mañana)
                            continue

                        # Si pasó todos los filtros, agregar el producto
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

            # Verificar si el servicio es de ayer
            fecha_servicio = servicio.fecha_agendamiento
            es_de_ayer = (fecha_servicio < hoy)

            item_data = {
                'servicio': servicio,
                'tipo': 'servicio',
                'nombre': servicio.servicio.nombre,
                'cliente': servicio.venta_reserva.cliente.nombre,
                'reserva_id': servicio.venta_reserva.id,
                'cantidad_personas': servicio.cantidad_personas or 1,
                'productos': productos_a_entregar,
                'es_proximo': False,  # Se marcará después
                'en_curso': getattr(servicio, 'en_curso', False),  # Si está en ejecución
                'es_pasado': getattr(servicio, 'es_pasado', False),  # Si ya terminó
                'es_de_ayer': es_de_ayer,  # Si es del día anterior
                'fecha_servicio': fecha_servicio.strftime('%d/%m/%Y'),  # Fecha formateada
                'hora_fin': getattr(servicio, 'hora_fin', None),  # Hora de finalización
                'duracion': servicio.servicio.duracion if servicio.servicio else None,  # Duración en minutos
                'estado_pago': estado_pago,
                'total': total,
                'pagado': pagado,
                'saldo_pendiente': saldo_pendiente,
                'estado_reserva': servicio.venta_reserva.estado_reserva  # Agregar estado de la reserva
            }

            # Agregar a la estructura correspondiente según el filtro
            if filtro_vista == 'pendientes_pago':
                # Agrupar por fecha y luego por hora
                fecha_key = fecha_servicio.strftime('%Y-%m-%d')
                agenda_por_fecha[fecha_key][hora_key].append(item_data)
            else:
                # Agrupar solo por hora
                agenda_por_hora[hora_key].append(item_data)

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

        # Agregar bloque de preparación de desayunos a las 17:10
        # Pero solo si aún no ha pasado la hora de fin (23:00)
        hora_inicio_prep = time(17, 10)
        hora_fin_prep = time(23, 0)

        # Determinar si está en curso
        en_curso_prep = hora_inicio_prep <= hora_actual <= hora_fin_prep

        # Solo agregar si es futuro o está en curso
        if hora_actual <= hora_fin_prep:
            # Si ya pasó la hora de inicio, agregarlo en la hora actual para que aparezca
            hora_key_prep = '17:10' if hora_actual < hora_inicio_prep else hora_actual.strftime('%H:%M')

            agenda_por_hora['17:10'].append({
                'tipo': 'preparacion_desayuno',
                'nombre': f'Preparación de Desayunos - {len(desayunos_info)} servicio(s) para mañana',
                'cliente': 'Múltiples clientes',
                'es_preparacion': True,
                'cantidad_desayunos': len(desayunos_info),
                'desayunos_detalle': desayunos_info,
                'es_proximo': False,
                'en_curso': en_curso_prep,
                'hora_fin': '23:00',
                'duracion': 350,  # 5 horas 50 minutos
                'estado_pago': 'preparacion',  # Estado especial
                'total': 0,
                'pagado': 0,
                'saldo_pendiente': 0
            })

    # Convertir a lista ordenada y marcar servicios urgentes
    agenda_ordenada = []
    hora_limite_urgente = (ahora + timedelta(minutes=30)).time()

    if filtro_vista == 'pendientes_pago':
        # Para pagos pendientes, organizar por fecha y hora con secciones claras
        ayer = hoy - timedelta(days=1)

        # Procesar primero servicios de AYER (si existen)
        ayer_key = ayer.strftime('%Y-%m-%d')
        if ayer_key in agenda_por_fecha:
            # Agregar header de sección para AYER
            agenda_ordenada.append({
                'tipo_seccion': 'header_fecha',
                'fecha': ayer,
                'fecha_texto': f"📅 AYER - {ayer.strftime('%A %d de %B, %Y')}",
                'es_ayer': True
            })

            # Agregar horas de ayer ordenadas
            for hora in sorted(agenda_por_fecha[ayer_key].keys()):
                hora_obj = datetime.strptime(hora, '%H:%M').time()
                agenda_ordenada.append({
                    'hora': hora,
                    'es_urgente': False,  # Servicios de ayer no son urgentes
                    'es_de_ayer': True,
                    'items': agenda_por_fecha[ayer_key][hora]
                })

        # Procesar servicios de HOY (si existen)
        hoy_key = hoy.strftime('%Y-%m-%d')
        if hoy_key in agenda_por_fecha:
            # Agregar header de sección para HOY
            agenda_ordenada.append({
                'tipo_seccion': 'header_fecha',
                'fecha': hoy,
                'fecha_texto': f"📅 HOY - {hoy.strftime('%A %d de %B, %Y')}",
                'es_hoy': True
            })

            # Agregar horas de hoy ordenadas
            for hora in sorted(agenda_por_fecha[hoy_key].keys()):
                hora_obj = datetime.strptime(hora, '%H:%M').time()
                es_urgente = hora_obj <= hora_limite_urgente
                agenda_ordenada.append({
                    'hora': hora,
                    'es_urgente': es_urgente,
                    'es_de_hoy': True,
                    'items': agenda_por_fecha[hoy_key][hora]
                })
    else:
        # Lógica normal: organizar solo por hora
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
        'debug_info': debug_info,
        'filtro_vista': filtro_vista  # Pasar filtro activo al template
    }

    return render(request, 'ventas/agenda_operativa.html', context)