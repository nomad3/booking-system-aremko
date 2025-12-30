import xlwt
from datetime import datetime, timedelta
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Sum, Count, F, Q
from django.db.models.functions import Coalesce # Added Coalesce import
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.contrib.auth.models import User
from django.db import models # Re-adding import just in case
from ..models import ReservaServicio, CategoriaServicio, Pago, VentaReserva, MovimientoCliente, ReservaProducto, Proveedor, Producto, Cliente # Relative imports, Added Cliente

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


@user_passes_test(es_administrador)
def productos_vendidos_view(request):
    """
    Vista para mostrar productos vendidos asociados a servicios de un día específico.
    Los productos se filtran según la fecha de agendamiento de los servicios en la reserva.
    """
    # Obtener la fecha actual con la zona horaria correcta
    hoy = timezone.localdate()

    # Obtener los parámetros del filtro, usando la fecha actual por defecto
    fecha_str = request.GET.get('fecha', hoy.strftime('%Y-%m-%d'))
    venta_reserva_id = request.GET.get('venta_reserva_id')

    # Convertir la fecha del parámetro a objeto de fecha
    try:
        fecha_filtro = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_filtro = hoy

    # Consultar todos los productos vendidos asociados a servicios del día
    # Lógica: Buscar VentaReserva que tengan servicios agendados para la fecha filtrada
    # y traer los productos asociados a esas reservas

    # Primero, obtener las VentaReserva que tienen servicios en la fecha especificada
    ventas_con_servicios_del_dia = VentaReserva.objects.filter(
        reservaservicios__fecha_agendamiento=fecha_filtro
    ).distinct().values_list('id', flat=True)

    # Ahora obtener los productos de esas ventas
    productos_vendidos = ReservaProducto.objects.select_related(
        'venta_reserva__cliente', 'producto'
    ).filter(
        venta_reserva_id__in=ventas_con_servicios_del_dia
    )

    # Filtrar por ID de VentaReserva si está presente y es un número válido
    if venta_reserva_id and venta_reserva_id.isdigit():
        productos_vendidos = productos_vendidos.filter(venta_reserva__id=int(venta_reserva_id))

    # Ordenar los productos vendidos por VentaReserva ID
    productos_vendidos = productos_vendidos.order_by('venta_reserva__id', 'producto__nombre')

    # Sumar el monto total de todos los productos vendidos
    total_monto_vendido = sum(
        (p.producto.precio_base * p.cantidad)
        for p in productos_vendidos if p.producto
    )

    # Preparar los datos para la tabla
    data = []
    for producto_reserva in productos_vendidos:
        # Skip if related product is missing
        if not producto_reserva.producto:
            continue

        valor_unitario = producto_reserva.producto.precio_base
        cantidad = producto_reserva.cantidad
        valor_total = valor_unitario * cantidad

        data.append({
            'venta_reserva_id': producto_reserva.venta_reserva.id if producto_reserva.venta_reserva else 'N/A',
            'cliente_nombre': producto_reserva.venta_reserva.cliente.nombre if producto_reserva.venta_reserva and producto_reserva.venta_reserva.cliente else 'N/A',
            'producto_nombre': producto_reserva.producto.nombre,
            'cantidad': cantidad,
            'valor_unitario': valor_unitario,
            'valor_total': valor_total,
        })

    # Pasar los datos a la plantilla
    context = {
        'productos': data,
        'fecha': fecha_filtro.strftime('%Y-%m-%d'),
        'venta_reserva_id': venta_reserva_id,
        'total_monto_vendido': total_monto_vendido,
        'total_productos': len(data),
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
        money_style = xlwt.easyxf(num_format_str='#,##0')

        # Headers
        headers = [
            'ID Venta/Reserva',
            'Cliente',
            'Producto',
            'Cantidad',
            'Valor Unitario',
            'Valor Total'
        ]

        for col, header in enumerate(headers):
            ws.write(0, col, header, header_style)
            ws.col(col).width = 256 * 20  # Ancho aproximado de 20 caracteres

        # Datos
        for row, producto_data in enumerate(data, 1):
            ws.write(row, 0, producto_data['venta_reserva_id'])
            ws.write(row, 1, producto_data['cliente_nombre'])
            ws.write(row, 2, producto_data['producto_nombre'])
            ws.write(row, 3, producto_data['cantidad'])
            ws.write(row, 4, producto_data['valor_unitario'], money_style)
            ws.write(row, 5, producto_data['valor_total'], money_style)

        wb.save(response)
        return response

    return render(request, 'ventas/productos_vendidos.html', context)


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
        'METODOS_PAGO': Pago.METODOS_PAGO,  # Añadir al contexto
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


def _get_combined_metrics_for_segmentation():
    """
    Helper para obtener métricas combinadas (servicios actuales + históricos) para segmentación
    Si la tabla histórica no existe, solo usa datos actuales.
    """
    from ventas.models import ServiceHistory
    from django.db import connection
    import logging

    logger = logging.getLogger(__name__)

    # Verificar si la tabla crm_service_history existe
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'crm_service_history'
                )
            """)
            table_exists = cursor.fetchone()[0]
    except Exception as e:
        logger.warning(f"Error checking table existence: {e}")
        table_exists = False

    if not table_exists:
        logger.info("Tabla crm_service_history no existe, usando solo datos actuales")
        # Solo usar datos actuales
        clientes = Cliente.objects.annotate(
            total_servicios=Count('ventareserva'),
            total_gasto=Coalesce(Sum('ventareserva__total'), 0, output_field=models.DecimalField())
        ).values('id', 'nombre', 'email', 'total_servicios', 'total_gasto')

        results = []
        for c in clientes:
            results.append({
                'cliente_id': c['id'],
                'nombre': c['nombre'],
                'email': c['email'],
                'servicios_actuales': c['total_servicios'],
                'gasto_actual': float(c['total_gasto']),
                'servicios_historicos': 0,
                'gasto_historico': 0,
                'total_servicios': c['total_servicios'],
                'total_gasto': float(c['total_gasto'])
            })
        return results

    # Tabla existe, usar query combinada AGRUPADA POR TELEFONO para consolidar duplicados
    try:
        query = """
        WITH clientes_por_telefono AS (
            -- Agrupar clientes por teléfono y elegir un representante
            SELECT
                telefono,
                MIN(id) as cliente_id_representante,
                MAX(nombre) as nombre,
                MAX(email) as email,
                ARRAY_AGG(id) as todos_los_ids
            FROM ventas_cliente
            WHERE telefono IS NOT NULL AND telefono != ''
            GROUP BY telefono
        )
        SELECT
            cpt.cliente_id_representante as cliente_id,
            cpt.nombre,
            cpt.email,
            cpt.telefono,
            -- Servicios actuales: SUMAR de TODOS los IDs con ese teléfono
            (SELECT COUNT(DISTINCT rs2.id)
             FROM ventas_ventareserva vr2
             JOIN ventas_reservaservicio rs2 ON vr2.id = rs2.venta_reserva_id
             WHERE vr2.cliente_id = ANY(cpt.todos_los_ids)
               AND vr2.estado_pago IN ('pagado', 'parcial')
            ) as servicios_actuales,
            -- Gasto actual: Usar el TOTAL de la VentaReserva (incluye descuentos/ajustes)
            (SELECT COALESCE(SUM(vr2.total), 0)
             FROM ventas_ventareserva vr2
             WHERE vr2.cliente_id = ANY(cpt.todos_los_ids)
               AND vr2.estado_pago IN ('pagado', 'parcial')
            ) as gasto_actual,
            -- Servicios históricos: SUMAR de TODOS los IDs con ese teléfono
            -- EXCLUIR servicios con fecha placeholder 2021-01-01 (importación histórica sin fecha real)
            (SELECT COUNT(DISTINCT sh2.id)
             FROM crm_service_history sh2
             WHERE sh2.cliente_id = ANY(cpt.todos_los_ids)
               AND sh2.service_date != '2021-01-01'
            ) as servicios_historicos,
            (SELECT COALESCE(SUM(sh2.price_paid), 0)
             FROM crm_service_history sh2
             WHERE sh2.cliente_id = ANY(cpt.todos_los_ids)
               AND sh2.service_date != '2021-01-01'
            ) as gasto_historico,
            -- Totales combinados
            ((SELECT COUNT(DISTINCT rs2.id)
              FROM ventas_ventareserva vr2
              JOIN ventas_reservaservicio rs2 ON vr2.id = rs2.venta_reserva_id
              WHERE vr2.cliente_id = ANY(cpt.todos_los_ids)
                AND vr2.estado_pago IN ('pagado', 'parcial')
             ) +
             (SELECT COUNT(DISTINCT sh2.id)
              FROM crm_service_history sh2
              WHERE sh2.cliente_id = ANY(cpt.todos_los_ids)
                AND sh2.service_date != '2021-01-01'
             )) as total_servicios,
            ((SELECT COALESCE(SUM(vr2.total), 0)
              FROM ventas_ventareserva vr2
              WHERE vr2.cliente_id = ANY(cpt.todos_los_ids)
                AND vr2.estado_pago IN ('pagado', 'parcial')
             ) +
             (SELECT COALESCE(SUM(sh2.price_paid), 0)
              FROM crm_service_history sh2
              WHERE sh2.cliente_id = ANY(cpt.todos_los_ids)
                AND sh2.service_date != '2021-01-01'
             )) as total_gasto
        FROM clientes_por_telefono cpt
        ORDER BY total_gasto DESC
        """

        with connection.cursor() as cursor:
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))

        return results
    except Exception as e:
        logger.error(f"Error ejecutando query combinada: {e}")
        # Fallback a solo datos actuales
        clientes = Cliente.objects.annotate(
            total_servicios=Count('ventareserva'),
            total_gasto=Coalesce(Sum('ventareserva__total'), 0, output_field=models.DecimalField())
        ).values('id', 'nombre', 'email', 'total_servicios', 'total_gasto')

        results = []
        for c in clientes:
            results.append({
                'cliente_id': c['id'],
                'nombre': c['nombre'],
                'email': c['email'],
                'servicios_actuales': c['total_servicios'],
                'gasto_actual': float(c['total_gasto']),
                'servicios_historicos': 0,
                'gasto_historico': 0,
                'total_servicios': c['total_servicios'],
                'total_gasto': float(c['total_gasto'])
            })
        return results

@login_required
def cliente_segmentation_view(request):
    """
    Displays client segmentation based ONLY on total spend (no visit count).
    Incluye tanto servicios actuales como históricos (CSV importados).
    """
    # Define Segmentation Thresholds (adjust as needed)
    SPEND_THRESHOLD_MEDIUM = 50000 # Example: 50,000 CLP
    SPEND_THRESHOLD_HIGH = 150000 # Example: 150,000 CLP

    # Obtener métricas combinadas (actuales + históricos)
    clientes_data = _get_combined_metrics_for_segmentation()

    # --- Categorize Clients (SOLO POR GASTO) ---
    segments = {
        'low_spend': {'count': 0, 'label': 'Bajo Gasto (< $50,000)'},
        'medium_spend': {'count': 0, 'label': 'Gasto Medio ($50,000 - $150,000)'},
        'high_spend': {'count': 0, 'label': 'Alto Gasto (> $150,000)'},
        'zero_spend': {'count': 0, 'label': 'Clientes Sin Gasto Registrado'},
    }

    for cliente_data in clientes_data:
        spend = cliente_data['total_gasto']

        if spend == 0:
             segments['zero_spend']['count'] += 1
             continue

        # Categorize ONLY by Spend
        if spend < SPEND_THRESHOLD_MEDIUM:
            segments['low_spend']['count'] += 1
        elif spend < SPEND_THRESHOLD_HIGH:
            segments['medium_spend']['count'] += 1
        else:
            segments['high_spend']['count'] += 1

    # Obtener comunas únicas para filtro personalizado (usando el nuevo campo estructurado)
    from ..models import Comuna
    comunas = Comuna.objects.filter(
        clientes__isnull=False  # Solo comunas que tienen clientes
    ).distinct().order_by('nombre').values('id', 'nombre')

    context = {
        'segments': segments,
        'total_clients': len(clientes_data),
        # Pass thresholds for display/info
        'spend_threshold_medium': SPEND_THRESHOLD_MEDIUM,
        'spend_threshold_high': SPEND_THRESHOLD_HIGH,
        # Filtro personalizado (ahora usando comunas estructuradas)
        'comunas': list(comunas),
    }

    return render(request, 'ventas/cliente_segmentation.html', context)

# New view to list clients by segment
@login_required
# @user_passes_test(es_administrador) # Optional: Restrict to admins if needed
def client_list_by_segment_view(request, segment_name):
    """
    Displays a list of clients for a specific segment (SOLO BASADO EN GASTO).
    Incluye tanto servicios actuales como históricos.
    """
    # Define Segmentation Thresholds
    SPEND_THRESHOLD_MEDIUM = 50000 # 50,000 CLP
    SPEND_THRESHOLD_HIGH = 150000 # 150,000 CLP

    # Obtener métricas combinadas
    clientes_data = _get_combined_metrics_for_segmentation()

    # Filtrar clientes según el segmento en Python (SOLO POR GASTO)
    filtered_client_ids = []

    for cliente_data in clientes_data:
        spend = cliente_data['total_gasto']

        include = False

        if segment_name == 'low_spend':
            include = 0 < spend < SPEND_THRESHOLD_MEDIUM
        elif segment_name == 'medium_spend':
            include = SPEND_THRESHOLD_MEDIUM <= spend < SPEND_THRESHOLD_HIGH
        elif segment_name == 'high_spend':
            include = spend >= SPEND_THRESHOLD_HIGH
        elif segment_name == 'zero_spend':
            include = spend == 0

        if include:
            filtered_client_ids.append(cliente_data['cliente_id'])

    # Convertir IDs filtrados de vuelta a queryset de Cliente
    if filtered_client_ids:
        clients = Cliente.objects.filter(id__in=filtered_client_ids).annotate(
            num_visits=Count('ventareserva'),
            total_spend=Coalesce(Sum('ventareserva__total'), 0, output_field=models.DecimalField())
        )
    else:
        clients = Cliente.objects.none()

    # Mapeo de nombres de segmento para el display
    segment_labels = {
        'low_spend': 'Bajo Gasto (< $50,000)',
        'medium_spend': 'Gasto Medio ($50,000 - $150,000)',
        'high_spend': 'Alto Gasto (> $150,000)',
        'zero_spend': 'Sin Gasto Registrado'
    }

    context = {
        'segment_name': segment_name,
        'segment_label': segment_labels.get(segment_name, segment_name),
        'clients': clients,
    }

    return render(request, 'ventas/client_list_by_segment.html', context)


@login_required
def client_list_custom_filter_view(request):
    """
    Vista para filtro personalizado de clientes por rango de gasto, comuna y email
    """
    # Obtener parámetros del formulario
    gasto_min = request.GET.get('gasto_min', '0')
    gasto_max = request.GET.get('gasto_max', '')
    comuna_id = request.GET.get('comuna', 'todas')  # Cambio de ciudad a comuna
    email_filter = request.GET.get('email_filter', 'todos')  # Nuevo filtro de email

    try:
        gasto_min = float(gasto_min) if gasto_min else 0
    except ValueError:
        gasto_min = 0

    try:
        gasto_max = float(gasto_max) if gasto_max else float('inf')
    except ValueError:
        gasto_max = float('inf')

    # Obtener métricas combinadas
    clientes_data = _get_combined_metrics_for_segmentation()

    # Filtrar por rango de gasto y crear mapas detallados
    filtered_client_ids = []
    gasto_map = {}  # {cliente_id: {'actual': X, 'historico': Y, 'total': Z}}

    for cliente_data in clientes_data:
        spend_total = cliente_data['total_gasto']
        spend_actual = cliente_data.get('gasto_actual', 0)
        spend_historico = cliente_data.get('gasto_historico', 0)

        if gasto_min <= spend_total <= gasto_max:
            filtered_client_ids.append(cliente_data['cliente_id'])
            gasto_map[cliente_data['cliente_id']] = {
                'actual': spend_actual,
                'historico': spend_historico,
                'total': spend_total
            }

    # Convertir a queryset y aplicar filtro de comuna
    if filtered_client_ids:
        clients = Cliente.objects.filter(id__in=filtered_client_ids)

        # Filtrar por comuna si no es "todas"
        if comuna_id and comuna_id != 'todas':
            clients = clients.filter(comuna_id=int(comuna_id))

        # Filtrar por email si se especificó
        from django.db.models import Q
        if email_filter == 'con_email':
            clients = clients.exclude(Q(email__isnull=True) | Q(email=''))
        elif email_filter == 'sin_email':
            clients = clients.filter(Q(email__isnull=True) | Q(email=''))

        # Agregar gastos detallados a cada cliente
        clients_list = []
        for cliente in clients:
            gastos = gasto_map.get(cliente.id, {'actual': 0, 'historico': 0, 'total': 0})
            cliente.gasto_actual = gastos['actual']
            cliente.gasto_historico = gastos['historico']
            cliente.gasto_total_combinado = gastos['total']
            clients_list.append(cliente)

        # Ordenar por gasto total descendente (mayor a menor)
        clients_list.sort(key=lambda c: c.gasto_total_combinado, reverse=True)

        clients = clients_list
    else:
        clients = []

    # Generar label descriptivo
    if gasto_max == float('inf'):
        segment_label = f'Gasto ≥ ${gasto_min:,.0f}'
    else:
        segment_label = f'Gasto: ${gasto_min:,.0f} - ${gasto_max:,.0f}'

    # Agregar nombre de comuna al label si está filtrado
    if comuna_id and comuna_id != 'todas':
        from ..models import Comuna
        try:
            comuna = Comuna.objects.get(id=int(comuna_id))
            segment_label += f' | Comuna: {comuna.nombre}'
        except Comuna.DoesNotExist:
            pass

    # Agregar filtro de email al label si está especificado
    if email_filter == 'con_email':
        segment_label += ' | Con email'
    elif email_filter == 'sin_email':
        segment_label += ' | Sin email'

    context = {
        'segment_name': 'custom_filter',
        'segment_label': segment_label,
        'clients': clients,
        'gasto_min': int(gasto_min) if gasto_min else 0,
        'gasto_max': int(gasto_max) if gasto_max != float('inf') else '',
        'comuna_id': comuna_id,
        'email_filter': email_filter,
        'is_custom_filter': True,
    }

    return render(request, 'ventas/client_list_by_segment.html', context)
