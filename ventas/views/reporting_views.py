import xlwt
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.db import models # Re-adding import just in case
from ..models import ReservaServicio, CategoriaServicio, Pago, VentaReserva, MovimientoCliente, ReservaProducto, Proveedor, Producto # Relative imports

# Helper function to check if the user is an administrator
def es_administrador(user):
    return user.is_staff or user.is_superuser

def servicios_vendidos_view(request):
    # Obtener la fecha actual con la zona horaria correcta
    hoy = timezone.localdate()

    # Obtener los parámetros del filtro, usando la fecha actual por defecto
    fecha_inicio_str = request.GET.get('fecha_inicio', hoy.strftime('%Y-%m-%d'))
    fecha_fin_str = request.GET.get('fecha_fin', hoy.strftime('%Y-%m-%d'))
    categoria_id = request.GET.get('categoria')
    venta_reserva_id = request.GET.get('venta_reserva_id')

    # Convertir las fechas de los parámetros a objetos de fecha
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = hoy

    try:
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_fin = hoy

    # Consultar todos los servicios vendidos, including assigned provider
    servicios_vendidos = ReservaServicio.objects.select_related(
        'venta_reserva__cliente', 'servicio__categoria', 'proveedor_asignado'
    )

    # Filtrar por rango de fechas usando date objects directly with __gte and __lte
    servicios_vendidos = servicios_vendidos.filter(
        fecha_agendamiento__gte=fecha_inicio,
        fecha_agendamiento__lte=fecha_fin
    )

    # Filtrar por categoría de servicio si está presente
    if categoria_id:
        servicios_vendidos = servicios_vendidos.filter(servicio__categoria_id=categoria_id)

    # Filtrar por ID de VentaReserva si está presente y es un número válido
    if venta_reserva_id and venta_reserva_id.isdigit():
        servicios_vendidos = servicios_vendidos.filter(venta_reserva__id=int(venta_reserva_id))

    # Ordenar los servicios vendidos
    servicios_vendidos = servicios_vendidos.order_by('-fecha_agendamiento', 'hora_inicio')

    # Obtener todas las categorías de servicio para el filtro
    categorias = CategoriaServicio.objects.all()

    # Sumar el monto total de todos los servicios vendidos que se están mostrando
    # Ensure related objects exist before calculation
    total_monto_vendido = sum(
        (s.servicio.precio_base * s.cantidad_personas)
        for s in servicios_vendidos if s.servicio
    )

    # Preparar los datos para la tabla
    data = []
    for servicio in servicios_vendidos:
        # Skip if related service is missing
        if not servicio.servicio:
            continue

        total_monto = servicio.servicio.precio_base * servicio.cantidad_personas

        # Use the date directly from the DateField
        fecha_display = servicio.fecha_agendamiento

        # Try to parse the time string, otherwise use the string
        hora_display_str = ''
        try:
            # Ensure hora_inicio is a string before parsing
            hora_inicio_str = str(servicio.hora_inicio) if servicio.hora_inicio is not None else ''
            if hora_inicio_str:
                 # Attempt parsing, fallback to original string on error
                 hora_display = datetime.strptime(hora_inicio_str, '%H:%M').time()
                 hora_display_str = hora_display.strftime('%H:%M')
            else:
                 hora_display_str = '' # Handle empty time
        except (ValueError, TypeError):
            hora_display_str = str(servicio.hora_inicio) # Fallback to original string

        data.append({
            'venta_reserva_id': servicio.venta_reserva.id if servicio.venta_reserva else 'N/A',
            'cliente_nombre': servicio.venta_reserva.cliente.nombre if servicio.venta_reserva and servicio.venta_reserva.cliente else 'N/A',
            'categoria_servicio': servicio.servicio.categoria.nombre if servicio.servicio.categoria else 'N/A',
            'servicio_nombre': servicio.servicio.nombre,
            'fecha_agendamiento': fecha_display, # Use processed date
            'hora_agendamiento_str': hora_display_str, # Use formatted string for display/export
            'monto': servicio.servicio.precio_base,
            'cantidad_personas': servicio.cantidad_personas,
            'total_monto': total_monto,
            'proveedor_asignado': servicio.proveedor_asignado.nombre if servicio.proveedor_asignado else 'N/A' # Add assigned provider name
        })

    # Pasar los datos y las categorías a la plantilla
    context = {
        'servicios': data,
        'categorias': categorias,
        'fecha_inicio': fecha_inicio.strftime('%Y-%m-%d'), # Pass formatted string
        'fecha_fin': fecha_fin.strftime('%Y-%m-%d'),     # Pass formatted string
        'categoria_id': categoria_id,
        'venta_reserva_id': venta_reserva_id,
        'total_monto_vendido': total_monto_vendido
    }

    # Verificar si se solicitó exportación
    if request.GET.get('export') == 'excel':
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="Servicios_Vendidos_{}.xls"'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )

        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Servicios Vendidos')

        # Estilos
        header_style = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray25;')
        date_style = xlwt.easyxf(num_format_str='DD/MM/YYYY')
        time_style = xlwt.easyxf(num_format_str='HH:MM')
        money_style = xlwt.easyxf(num_format_str='#,##0')

        # Headers
        headers = [
            'ID Venta/Reserva',
            'Cliente',
            'Categoría del Servicio',
            'Servicio',
            'Fecha de Agendamiento',
            'Hora de Agendamiento',
            'Cantidad de Personas',
            'Monto Total',
            'Proveedor Asignado' # Add new header
        ]

        for col, header in enumerate(headers):
            ws.write(0, col, header, header_style)
            ws.col(col).width = 256 * 20  # Ancho aproximado de 20 caracteres

        # Datos
        for row, servicio_data in enumerate(data, 1): # Use data dict
            ws.write(row, 0, servicio_data['venta_reserva_id'])
            ws.write(row, 1, servicio_data['cliente_nombre'])
            ws.write(row, 2, servicio_data['categoria_servicio'])
            ws.write(row, 3, servicio_data['servicio_nombre'])
            ws.write(row, 4, servicio_data['fecha_agendamiento'], date_style) # Use date object
            ws.write(row, 5, servicio_data['hora_agendamiento_str']) # Use string for Excel time
            ws.write(row, 6, servicio_data['cantidad_personas'])
            ws.write(row, 7, servicio_data['total_monto'], money_style)
            ws.write(row, 8, servicio_data['proveedor_asignado']) # Add provider data to Excel

        wb.save(response)
        return response

    return render(request, 'ventas/servicios_vendidos.html', context)


@user_passes_test(es_administrador)  # Restringir el acceso a administradores
def caja_diaria_view(request):
    # Obtener rango de fechas desde los parámetros GET
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    metodo_pago = request.GET.get('metodo_pago')  # Nuevo filtro
    usuario_id = request.GET.get('usuario') # Get selected user ID

    # Establecer fechas por defecto (hoy) si no se proporcionan
    today = timezone.localdate()
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Parsear las cadenas de fecha a objetos date
    try:
        fecha_inicio_parsed = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin_parsed = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        # Manejar errores de formato de fecha, revertir a hoy
        fecha_inicio_parsed = today
        fecha_fin_parsed = today
        fecha_inicio_str = today.strftime('%Y-%m-%d')
        fecha_fin_str = today.strftime('%Y-%m-%d')


    # Validar que fecha_inicio no es posterior a fecha_fin
    if fecha_inicio_parsed > fecha_fin_parsed:
        fecha_inicio_parsed, fecha_fin_parsed = fecha_fin_parsed, fecha_inicio_parsed
        fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str

    # Ajustar fecha_fin para incluir todo el día (make_aware for timezone)
    fecha_inicio_dt = timezone.make_aware(datetime.combine(fecha_inicio_parsed, datetime.min.time()))
    fecha_fin_dt = timezone.make_aware(datetime.combine(fecha_fin_parsed, datetime.max.time())) # Use max time

    # Obtener todos los usuarios activos para el filtro
    usuarios = User.objects.filter(is_active=True).order_by('username')

    # Filtrar Pago basado en fecha_pago (using timezone-aware datetimes)
    pagos = Pago.objects.filter(
        fecha_pago__range=(fecha_inicio_dt, fecha_fin_dt)
    ).select_related('venta_reserva__cliente', 'usuario') # Optimize queries

    # Filtrar los pagos por usuario si se ha seleccionado uno
    if usuario_id:
        pagos = pagos.filter(usuario_id=usuario_id)
    else:
        usuario_id = '' # Ensure it's a string for context

    # Filtrar por método de pago si se ha seleccionado uno
    if metodo_pago:
        pagos = pagos.filter(metodo_pago=metodo_pago)
    else:
        metodo_pago = '' # Ensure it's a string for context

    # Calculate totals from the filtered payments
    total_pagos = pagos.aggregate(total=Sum('monto'))['total'] or 0

    # Agrupar pagos por método de pago y contar transacciones
    pagos_grouped = pagos.values('metodo_pago').annotate(
        total_monto=Sum('monto'),
        cantidad_transacciones=Count('id')
    ).order_by('metodo_pago')

    # Obtener los métodos de pago para el filtro
    METODOS_PAGO = Pago.METODOS_PAGO

    context = {
        # 'ventas': ventas, # Removed as it wasn't directly used and potentially inefficient
        'pagos': pagos, # Pass the filtered payments
        # 'total_ventas': total_ventas, # Removed
        'total_pagos': total_pagos,
        'fecha_inicio': fecha_inicio_str, # Pass string dates back to template
        'fecha_fin': fecha_fin_str,
        'pagos_grouped': pagos_grouped,
        'usuarios': usuarios,
        'usuario_id': usuario_id, # Pass selected user ID
        'metodo_pago': metodo_pago,  # Añadir al contexto
        'METODOS_PAGO': METODOS_PAGO,  # Añadir al contexto
    }

    return render(request, 'ventas/caja_diaria.html', context)


def caja_diaria_recepcionistas_view(request):
    # Lista de usuarios permitidos (por username)
    usuarios_permitidos_usernames = ['Lina', 'Edson', 'Ernesto', 'Rafael']
    usuarios_permitidos = User.objects.filter(username__in=usuarios_permitidos_usernames, is_active=True).order_by('username')

    # Obtener rango de fechas y filtros
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    metodo_pago = request.GET.get('metodo_pago')
    usuario_id = request.GET.get('usuario')

    # Establecer fechas por defecto
    today = timezone.localdate()
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Parsear fechas
    try:
        fecha_inicio_parsed = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin_parsed = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio_parsed = today
        fecha_fin_parsed = today
        fecha_inicio_str = today.strftime('%Y-%m-%d')
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Validar fechas
    if fecha_inicio_parsed > fecha_fin_parsed:
        fecha_inicio_parsed, fecha_fin_parsed = fecha_fin_parsed, fecha_inicio_parsed
        fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str

    # Ajustar fecha_fin (make_aware for timezone)
    fecha_inicio_dt = timezone.make_aware(datetime.combine(fecha_inicio_parsed, datetime.min.time()))
    fecha_fin_dt = timezone.make_aware(datetime.combine(fecha_fin_parsed, datetime.max.time()))

    # Filtrar pagos by allowed users and date range
    pagos = Pago.objects.filter(
        fecha_pago__range=(fecha_inicio_dt, fecha_fin_dt),
        usuario__in=usuarios_permitidos # Filter by the allowed users queryset
    ).select_related('venta_reserva__cliente', 'usuario') # Optimize

    # Apply optional user filter (among the allowed ones)
    if usuario_id:
        pagos = pagos.filter(usuario_id=usuario_id)

    # Apply optional payment method filter
    if metodo_pago:
        pagos = pagos.filter(metodo_pago=metodo_pago)

    # Calcular total pagos
    total_pagos = pagos.aggregate(total=Sum('monto'))['total'] or 0

    # Agrupar pagos
    pagos_grouped = pagos.values('metodo_pago').annotate(
        total_monto=Sum('monto'),
        cantidad_transacciones=Count('id')
    ).order_by('metodo_pago')

    # Contexto
    context = {
        # 'ventas': ventas, # Removed
        'pagos': pagos,
        # 'total_ventas': total_ventas, # Removed
        'total_pagos': total_pagos,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'pagos_grouped': pagos_grouped,
        'usuarios': usuarios_permitidos, # Pass the filtered list of allowed users
        'usuario_id': usuario_id or '',
        'metodo_pago': metodo_pago or '',
        'METODOS_PAGO': Pago.METODOS_PAGO,
    }

    return render(request, 'ventas/caja_diaria_recepcionistas.html', context)


@login_required
def productos_vendidos(request):
    # Obtener fechas del request
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    proveedor_id = request.GET.get('proveedor')
    producto_id = request.GET.get('producto')

    # Establecer fechas por defecto si no se proporcionan
    today = timezone.localdate()
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Parsear fechas
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio = today
        fecha_fin = today
        fecha_inicio_str = today.strftime('%Y-%m-%d')
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Validar fechas
    if fecha_inicio > fecha_fin:
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio
        fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str

    # Construir la consulta base
    productos_query = ReservaProducto.objects.select_related(
        'venta_reserva__cliente',
        'producto__categoria', # Added categoria
        'producto__proveedor' # Added proveedor
    ).filter(
        venta_reserva__fecha_reserva__date__range=[fecha_inicio, fecha_fin] # Filter on date part
    )

    # Aplicar filtros adicionales solo si se proporcionan valores válidos
    if proveedor_id and proveedor_id.strip():
        productos_query = productos_query.filter(producto__proveedor_id=proveedor_id)

    if producto_id and producto_id.strip():
        productos_query = productos_query.filter(producto_id=producto_id)

    # Calcular totales using aggregate on the filtered queryset
    totales = productos_query.aggregate(
        total_cantidad_productos=Sum('cantidad'),
        total_monto_periodo=Sum(F('cantidad') * F('producto__precio_base'), output_field=models.DecimalField())
    )

    # Obtener los resultados ordenados
    productos_vendidos_list = productos_query.order_by('-venta_reserva__fecha_reserva')

    # Obtener listas para los filtros
    todos_proveedores = Proveedor.objects.all().order_by('nombre')
    todos_productos = Producto.objects.all().order_by('nombre')

    context = {
        'productos_vendidos': productos_vendidos_list, # Pass the queryset
        'proveedores': todos_proveedores,
        'productos_lista': todos_productos,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'proveedor_id': proveedor_id if proveedor_id else '',
        'producto_id': producto_id if producto_id else '',
        'total_cantidad_productos': totales['total_cantidad_productos'] or 0,
        'total_monto_periodo': totales['total_monto_periodo'] or 0,
    }

    # Verificar si se solicitó exportación
    if request.GET.get('export') == 'excel':
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="Productos_Vendidos_{}.xls"'.format(
            datetime.now().strftime('%Y%m%d_%H%M%S')
        )

        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Productos Vendidos')

        # Estilos
        header_style = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray25;')
        date_style = xlwt.easyxf(num_format_str='DD/MM/YYYY HH:MM')
        money_style = xlwt.easyxf(num_format_str='#,##0')

        # Headers
        headers = [
            'ID Venta/Reserva',
            'Cliente',
            'Fecha Venta',
            'Proveedor',
            'Producto',
            'Cantidad',
            'Precio Unitario',
            'Monto Total'
        ]

        for col, header in enumerate(headers):
            ws.write(0, col, header, header_style)
            ws.col(col).width = 256 * 20

        # Datos - Iterate over the queryset directly
        for row, rp in enumerate(productos_vendidos_list, 1):
            monto_total = rp.cantidad * rp.producto.precio_base

            # Convertir la fecha a zona horaria local
            fecha_venta = timezone.localtime(rp.venta_reserva.fecha_reserva) if rp.venta_reserva else None

            ws.write(row, 0, rp.venta_reserva.id if rp.venta_reserva else 'N/A')
            ws.write(row, 1, rp.venta_reserva.cliente.nombre if rp.venta_reserva and rp.venta_reserva.cliente else 'N/A')
            ws.write(row, 2, fecha_venta, date_style) # Use datetime object with style
            ws.write(row, 3, rp.producto.proveedor.nombre if rp.producto.proveedor else 'N/A')
            ws.write(row, 4, rp.producto.nombre)
            ws.write(row, 5, rp.cantidad)
            ws.write(row, 6, rp.producto.precio_base, money_style)
            ws.write(row, 7, monto_total, money_style)

        wb.save(response)
        return response

    return render(request, 'ventas/productos_vendidos.html', context)


@user_passes_test(es_administrador)  # Restringir el acceso a administradores
def auditoria_movimientos_view(request):
    # Obtener parámetros del filtro
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    usuario_username = request.GET.get('usuario') # Get username from filter

    # Establecer fechas por defecto si no se proporcionan
    today = timezone.localdate()
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Convertir fechas a objetos datetime aware
    try:
        fecha_inicio_dt = timezone.make_aware(datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        # Add timedelta(days=1) to include the whole end day, or use max.time()
        fecha_fin_dt = timezone.make_aware(datetime.combine(datetime.strptime(fecha_fin_str, '%Y-%m-%d').date(), datetime.max.time()))
    except ValueError:
        fecha_inicio_dt = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        fecha_fin_dt = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        fecha_inicio_str = today.strftime('%Y-%m-%d')
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Validar fechas
    if fecha_inicio_dt > fecha_fin_dt:
         fecha_inicio_dt, fecha_fin_dt = fecha_fin_dt, fecha_inicio_dt
         fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str


    # Iniciar el queryset base
    movimientos = MovimientoCliente.objects.select_related(
        'cliente', 'usuario', 'venta_reserva'
    )

    # Aplicar filtros
    movimientos = movimientos.filter(
        fecha_movimiento__range=(fecha_inicio_dt, fecha_fin_dt) # Use aware datetimes
    )

    if tipo_movimiento:
        movimientos = movimientos.filter(tipo_movimiento__icontains=tipo_movimiento)

    # Filtro de usuario por username
    if usuario_username and usuario_username != '':
        movimientos = movimientos.filter(usuario__username__exact=usuario_username)

    # Ordenar por fecha descendente
    movimientos = movimientos.order_by('-fecha_movimiento')

    # Paginación
    paginator = Paginator(movimientos, 100) # 100 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'movimientos': page_obj, # Pass the page object
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'tipo_movimiento': tipo_movimiento or '', # Ensure not None
        'usuario_username': usuario_username or '', # Ensure not None
        'usuarios': User.objects.filter(is_active=True).order_by('username'),  # Solo usuarios activos for filter dropdown
    }

    return render(request, 'ventas/auditoria_movimientos.html', context)


@login_required
# @user_passes_test(es_administrador) # Optional: Restrict to admins if needed
def cliente_segmentation_view(request):
    """
    Displays client segmentation based on visit count and total spend.
    """
    # Define Segmentation Thresholds (adjust as needed)
    VISIT_THRESHOLD_REGULAR = 2
    VISIT_THRESHOLD_VIP = 6 # Example: 6 or more visits
    SPEND_THRESHOLD_MEDIUM = 50000 # Example: 50,000 CLP
    SPEND_THRESHOLD_HIGH = 150000 # Example: 150,000 CLP

    # Annotate clients with visit count and total spend
    # Use Coalesce to handle clients with no spending (Sum returns None)
    clientes_annotated = Cliente.objects.annotate(
        num_visits=Count('ventareserva'),
        total_spend=models.Coalesce(Sum('ventareserva__total'), 0, output_field=models.DecimalField())
    ).order_by('-total_spend') # Order for potential display

    # --- Categorize Clients ---
    segments = {
        'new_low_spend': {'count': 0, 'label': 'Nuevos (0-1 Visita, Bajo Gasto)'},
        'new_medium_spend': {'count': 0, 'label': 'Nuevos (0-1 Visita, Gasto Medio)'},
        'new_high_spend': {'count': 0, 'label': 'Nuevos (0-1 Visita, Alto Gasto)'},
        'regular_low_spend': {'count': 0, 'label': f'Regulares ({VISIT_THRESHOLD_REGULAR}-{VISIT_THRESHOLD_VIP-1} Visitas, Bajo Gasto)'},
        'regular_medium_spend': {'count': 0, 'label': f'Regulares ({VISIT_THRESHOLD_REGULAR}-{VISIT_THRESHOLD_VIP-1} Visitas, Gasto Medio)'},
        'regular_high_spend': {'count': 0, 'label': f'Regulares ({VISIT_THRESHOLD_REGULAR}-{VISIT_THRESHOLD_VIP-1} Visitas, Alto Gasto)'},
        'vip_low_spend': {'count': 0, 'label': f'VIP (>{VISIT_THRESHOLD_VIP-1} Visitas, Bajo Gasto)'},
        'vip_medium_spend': {'count': 0, 'label': f'VIP (>{VISIT_THRESHOLD_VIP-1} Visitas, Gasto Medio)'},
        'vip_high_spend': {'count': 0, 'label': f'VIP (>{VISIT_THRESHOLD_VIP-1} Visitas, Alto Gasto)'},
        'zero_spend': {'count': 0, 'label': 'Clientes Sin Gasto Registrado'}, # Clients with no VentaReserva
    }

    for cliente in clientes_annotated:
        visits = cliente.num_visits
        spend = cliente.total_spend

        if visits == 0 and spend == 0:
             segments['zero_spend']['count'] += 1
             continue # Skip further categorization if no visits/spend

        # Categorize by Visits
        if visits < VISIT_THRESHOLD_REGULAR: # 0-1 visits
            visit_category = 'new'
        elif visits < VISIT_THRESHOLD_VIP: # 2-5 visits (example)
            visit_category = 'regular'
        else: # 6+ visits
            visit_category = 'vip'

        # Categorize by Spend
        if spend < SPEND_THRESHOLD_MEDIUM:
            spend_category = 'low_spend'
        elif spend < SPEND_THRESHOLD_HIGH:
            spend_category = 'medium_spend'
        else:
            spend_category = 'high_spend'

        # Increment the combined segment count
        segment_key = f"{visit_category}_{spend_category}"
        if segment_key in segments:
            segments[segment_key]['count'] += 1
        else:
             # This case shouldn't happen with the current logic, but good for safety
             logger.warning(f"Unexpected segment key generated: {segment_key} for client {cliente.id}")


    context = {
        'segments': segments,
        'total_clients': clientes_annotated.count(),
        # Pass thresholds for display/info
        'visit_threshold_regular': VISIT_THRESHOLD_REGULAR,
        'visit_threshold_vip': VISIT_THRESHOLD_VIP,
        'spend_threshold_medium': SPEND_THRESHOLD_MEDIUM,
        'spend_threshold_high': SPEND_THRESHOLD_HIGH,
    }

    return render(request, 'ventas/cliente_segmentation.html', context)
