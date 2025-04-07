from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.db.models import Sum, F, Q
from datetime import datetime, timedelta
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from ..models import DetalleCompra, Proveedor, Producto, Compra, VentaReserva, CategoriaServicio, Servicio, Cliente # Relative imports

def detalle_compra_list(request):
    # Obtener la fecha actual
    today = timezone.localdate()

    # Obtener filtros de los parámetros GET
    proveedor_id = request.GET.get('proveedor')
    producto_id = request.GET.get('producto')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    # Establecer fechas por defecto si no se proporcionan
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Convertir cadenas de fecha a objetos date
    try:
        fecha_inicio_obj = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio_obj = today
        fecha_inicio_str = today.strftime('%Y-%m-%d')

    try:
        fecha_fin_obj = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_fin_obj = today
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Validar fechas
    if fecha_inicio_obj > fecha_fin_obj:
        fecha_inicio_obj, fecha_fin_obj = fecha_fin_obj, fecha_inicio_obj
        fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str

    # Filtrar DetalleCompra con todos los filtros
    detalles = DetalleCompra.objects.select_related(
        'compra__proveedor', 'producto'
    ).filter(
        compra__fecha_compra__range=[fecha_inicio_obj, fecha_fin_obj]
    )

    # Aplicar filtro por proveedor si se proporciona
    if proveedor_id and proveedor_id.isdigit():
        detalles = detalles.filter(compra__proveedor_id=int(proveedor_id))

    # Aplicar filtro por producto si se proporciona
    if producto_id and producto_id.isdigit():
        detalles = detalles.filter(producto_id=int(producto_id))

    # Eliminar duplicados si los filtros causan joins múltiples
    detalles = detalles.distinct()

    # Calcular el total en el rango de fechas
    total_en_rango = detalles.aggregate(
        total=Sum(F('cantidad') * F('precio_unitario'), output_field=models.DecimalField())
    )['total'] or 0

    context = {
        'detalles_compras': detalles,
        'proveedores': Proveedor.objects.all(),
        'productos': Producto.objects.all(),
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'proveedor_id': proveedor_id,
        'producto_id': producto_id,
        'total_en_rango': total_en_rango,
    }

    return render(request, 'ventas/detalle_compra_list.html', context)

def detalle_compra_detail(request, pk):
    # Obtener el detalle de compra específico
    detalle = get_object_or_404(DetalleCompra.objects.select_related(
        'compra',
        'compra__proveedor',
        'producto'
    ), pk=pk)

    # Obtener la compra asociada y todos sus detalles
    compra = detalle.compra
    todos_los_detalles = compra.detalles.select_related('producto').all()

    context = {
        'detalle_actual': detalle,
        'compra': compra,
        'detalles': todos_los_detalles,
    }

    return render(request, 'ventas/detalle_compra_detail.html', context)

def compra_list(request):
    # Obtener la fecha actual
    today = timezone.localdate()

    # Obtener filtros de los parámetros GET
    proveedor_id = request.GET.get('proveedor')
    producto_id = request.GET.get('producto')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    # Establecer fechas por defecto si no se proporcionan
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Convertir cadenas de fecha a objetos datetime
    try:
        fecha_inicio_parsed = datetime.strptime(fecha_inicio_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio_parsed = today
        fecha_inicio_str = today.strftime('%Y-%m-%d')

    try:
        fecha_fin_parsed = datetime.strptime(fecha_fin_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_fin_parsed = today
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Validar fechas
    if fecha_inicio_parsed > fecha_fin_parsed:
        fecha_inicio_parsed, fecha_fin_parsed = fecha_fin_parsed, fecha_inicio_parsed
        fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str

    # Filtrar Compras por rango de fechas
    compras = Compra.objects.filter(
        fecha_compra__range=(fecha_inicio_parsed, fecha_fin_parsed)
    ).select_related('proveedor').prefetch_related('detalles__producto')

    # Aplicar filtro por proveedor si se proporciona
    if proveedor_id and proveedor_id.isdigit():
        compras = compras.filter(proveedor_id=int(proveedor_id))

    # Aplicar filtro por producto si se proporciona
    if producto_id and producto_id.isdigit():
        compras = compras.filter(detalles__producto_id=int(producto_id))

    # Eliminar duplicados si los filtros causan joins múltiples
    compras = compras.distinct()

    # Calcular el total en el rango de fechas
    total_en_rango = compras.aggregate(total=Sum('total'))['total'] or 0

    # Obtener todos los proveedores y productos para los filtros
    proveedores = Proveedor.objects.all()
    productos = Producto.objects.all()

    context = {
        'compras': compras,
        'proveedores': proveedores,
        'productos': productos,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'proveedor_id': proveedor_id,
        'producto_id': producto_id,
        'total_en_rango': total_en_rango,
    }

    return render(request, 'ventas/compra_list.html', context)

def compra_detail(request, pk):
    compra = get_object_or_404(Compra.objects.select_related('proveedor').prefetch_related('detalles__producto'), pk=pk)
    detalles = compra.detalles.all() # Already prefetched

    context = {
        'compra': compra,
        'detalles': detalles,
    }

    return render(request, 'ventas/compra_detail.html', context)

def venta_reserva_list(request):
    # Get current date
    today = timezone.localdate()

    # Get filters from GET parameters
    categoria_servicio_id = request.GET.get('categoria_servicio')
    servicio_id = request.GET.get('servicio')
    fecha_inicio_str = request.GET.get('fecha_inicio')
    fecha_fin_str = request.GET.get('fecha_fin')

    # If fecha_inicio or fecha_fin are not provided, set them to today's date
    if not fecha_inicio_str:
        fecha_inicio_str = today.strftime('%Y-%m-%d')
    if not fecha_fin_str:
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Parse the date strings to date objects with timezone awareness
    try:
        fecha_inicio_parsed = timezone.make_aware(datetime.strptime(fecha_inicio_str, '%Y-%m-%d'))
        # Use max time for end date to include the whole day
        fecha_fin_parsed = timezone.make_aware(datetime.combine(datetime.strptime(fecha_fin_str, '%Y-%m-%d').date(), datetime.max.time()))
    except ValueError:
        fecha_inicio_parsed = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        fecha_fin_parsed = timezone.make_aware(datetime.combine(today, datetime.max.time()))
        fecha_inicio_str = today.strftime('%Y-%m-%d')
        fecha_fin_str = today.strftime('%Y-%m-%d')

    # Validate dates
    if fecha_inicio_parsed > fecha_fin_parsed:
        fecha_inicio_parsed, fecha_fin_parsed = fecha_fin_parsed, fecha_inicio_parsed
        fecha_inicio_str, fecha_fin_str = fecha_fin_str, fecha_inicio_str

    # Build the queryset with select_related and prefetch_related
    qs = VentaReserva.objects.select_related('cliente').prefetch_related(
        'reservaservicios__servicio__categoria', # Prefetch category as well
        'reservaproductos__producto',
        'pagos' # Prefetch payments
    )

    # Apply date range filter (inclusive of the end date)
    qs = qs.filter(fecha_reserva__range=(fecha_inicio_parsed, fecha_fin_parsed))

    # Apply filters based on category and service
    if categoria_servicio_id and categoria_servicio_id.isdigit():
        qs = qs.filter(reservaservicios__servicio__categoria_id=int(categoria_servicio_id))
    if servicio_id and servicio_id.isdigit():
        qs = qs.filter(reservaservicios__servicio_id=int(servicio_id))

    # Remove duplicates if joins create duplicates
    qs = qs.distinct()

    # Calculate total in the date range from the filtered queryset
    total_en_rango = qs.aggregate(total=Sum('total'))['total'] or 0

    # Get categories and services for the filter form
    categorias_servicio = CategoriaServicio.objects.all()
    servicios = Servicio.objects.all()

    context = {
        'venta_reservas': qs,
        'categorias_servicio': categorias_servicio,
        'servicios': servicios,
        'fecha_inicio': fecha_inicio_str,
        'fecha_fin': fecha_fin_str,
        'categoria_servicio_id': categoria_servicio_id,
        'servicio_id': servicio_id,
        'total_en_rango': total_en_rango,
    }

    return render(request, 'ventas/venta_reserva_list.html', context)

def venta_reserva_detail(request, pk):
    venta = get_object_or_404(
        VentaReserva.objects.prefetch_related(
            'reservaservicios__servicio',
            'reservaproductos__producto',
            'pagos',
            'cliente',
        ),
        pk=pk,
    )

    context = {
        'venta': venta,
    }
    return render(request, 'ventas/venta_reserva_detail.html', context)


@login_required
def lista_clientes(request):
    search_query = request.GET.get('search', '')

    # Filtrar clientes según la búsqueda
    clientes = Cliente.objects.all().order_by('nombre')
    if search_query:
        clientes = clientes.filter(
            Q(nombre__icontains=search_query) |
            Q(telefono__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    # Configurar paginación
    paginator = Paginator(clientes, 25)  # 25 clientes por página
    page = request.GET.get('page')
    clientes_paginados = paginator.get_page(page)

    context = {
        'clientes': clientes_paginados,
        'is_paginated': paginator.num_pages > 1,
        'page_obj': clientes_paginados,
        'search_query': search_query,  # Añadido para mantener el valor de búsqueda
    }

    # Asegurarse de que se está renderizando el template HTML
    return render(request, 'ventas/lista_clientes.html', context)
