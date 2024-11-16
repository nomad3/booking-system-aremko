from rest_framework import viewsets
from rest_framework.response import Response
from django.db.models import Sum, Q, Count, F
from django.contrib.auth.decorators import user_passes_test
import csv
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto, Cliente, Pago, CategoriaServicio, Servicio, ReservaServicio, MovimientoCliente, Compra, DetalleCompra 
from .utils import verificar_disponibilidad
from django.utils.timezone import make_aware
from django.utils.dateparse import parse_date
from django.db import models
from django.db.models import Q, Sum
from django.db import transaction
from rest_framework.exceptions import ValidationError
from django.contrib.auth.models import User
from .serializers import (
    ProveedorSerializer,
    CategoriaProductoSerializer,
    ProductoSerializer,
    VentaReservaSerializer,
    ClienteSerializer,
    PagoSerializer,
    ReservaProductoSerializer,
    ServicioSerializer,
    ReservaServicioSerializer,
    CategoriaServicioSerializer,
    VentaReservaSerializer
)


def detalle_compra_list(request):
    # Obtener la fecha actual
    today = timezone.localdate()

    # Obtener filtros de los parámetros GET
    proveedor_id = request.GET.get('proveedor')
    producto_id = request.GET.get('producto')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Establecer fechas por defecto si no se proporcionan
    if not fecha_inicio:
        fecha_inicio = today.strftime('%Y-%m-%d')
    if not fecha_fin:
        fecha_fin = today.strftime('%Y-%m-%d')

    # Convertir cadenas de fecha a objetos date
    try:
        fecha_inicio_obj = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio_obj = today

    try:
        fecha_fin_obj = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    except ValueError:
        fecha_fin_obj = today

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
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
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
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Establecer fechas por defecto si no se proporcionan
    if not fecha_inicio:
        fecha_inicio = today.strftime('%Y-%m-%d')
    if not fecha_fin:
        fecha_fin = today.strftime('%Y-%m-%d')

    # Convertir cadenas de fecha a objetos datetime
    try:
        fecha_inicio_parsed = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio_parsed = today

    try:
        fecha_fin_parsed = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    except ValueError:
        fecha_fin_parsed = today

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
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'proveedor_id': proveedor_id,
        'producto_id': producto_id,
        'total_en_rango': total_en_rango,
    }

    return render(request, 'ventas/compra_list.html', context)

def compra_detail(request, pk):
    compra = get_object_or_404(Compra, pk=pk)
    detalles = compra.detalles.select_related('producto')

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
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # If fecha_inicio or fecha_fin are not provided, set them to today's date
    if not fecha_inicio:
        fecha_inicio = today.strftime('%Y-%m-%d')
    if not fecha_fin:
        fecha_fin = today.strftime('%Y-%m-%d')

    # Parse the date strings to date objects with timezone awareness
    fecha_inicio_parsed = timezone.make_aware(datetime.strptime(fecha_inicio, '%Y-%m-%d'))
    fecha_fin_parsed = timezone.make_aware(datetime.strptime(fecha_fin, '%Y-%m-%d')) + timedelta(days=1)

    # Build the queryset with select_related and prefetch_related
    qs = VentaReserva.objects.select_related('cliente').prefetch_related(
        'reservaservicios__servicio',
        'reservaproductos__producto',
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

    # Calculate total in the date range
    total_en_rango = qs.aggregate(total=Sum('total'))['total'] or 0

    # Get categories and services for the filter form
    categorias_servicio = CategoriaServicio.objects.all()
    servicios = Servicio.objects.all()

    context = {
        'venta_reservas': qs,
        'categorias_servicio': categorias_servicio,
        'servicios': servicios,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
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

def servicios_vendidos_view(request):
    # Obtener la fecha actual con la zona horaria correcta
    hoy = timezone.localdate()

    # Obtener los parámetros del filtro, usando la fecha actual por defecto
    fecha_inicio = request.GET.get('fecha_inicio', hoy)
    fecha_fin = request.GET.get('fecha_fin', hoy)
    categoria_id = request.GET.get('categoria')
    venta_reserva_id = request.GET.get('venta_reserva_id')

    # Convertir las fechas de los parámetros a objetos de fecha si son strings
    if isinstance(fecha_inicio, str):
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()

    if isinstance(fecha_fin, str):
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

    # Convertir las fechas de inicio y fin a objetos datetime con zona horaria local
    fecha_inicio_dt = timezone.make_aware(datetime.combine(fecha_inicio, datetime.min.time()))
    fecha_fin_dt = timezone.make_aware(datetime.combine(fecha_fin, datetime.max.time()))

    # Consultar todos los servicios vendidos
    servicios_vendidos = ReservaServicio.objects.select_related('venta_reserva__cliente', 'servicio__categoria')

    # Filtrar por rango de fechas (usando __gte y __lte para comparar correctamente)
    servicios_vendidos = servicios_vendidos.filter(fecha_agendamiento__gte=fecha_inicio_dt, fecha_agendamiento__lte=fecha_fin_dt)

    # Filtrar por categoría de servicio si está presente
    if categoria_id:
        servicios_vendidos = servicios_vendidos.filter(servicio__categoria_id=categoria_id)

    # Filtrar por ID de VentaReserva si está presente y es un número válido
    if venta_reserva_id and venta_reserva_id.isdigit():
        servicios_vendidos = servicios_vendidos.filter(venta_reserva__id=int(venta_reserva_id))

    # Ordenar los servicios vendidos
    servicios_vendidos = servicios_vendidos.order_by('-fecha_agendamiento__date', 'fecha_agendamiento__time')

    # Obtener todas las categorías de servicio para el filtro
    categorias = CategoriaServicio.objects.all()

    # Sumar el monto total de todos los servicios vendidos que se están mostrando
    total_monto_vendido = sum(servicio.servicio.precio_base * servicio.cantidad_personas for servicio in servicios_vendidos)

    # Preparar los datos para la tabla
    data = []
    for servicio in servicios_vendidos:
        total_monto = servicio.servicio.precio_base * servicio.cantidad_personas
        fecha_agendamiento = timezone.localtime(servicio.fecha_agendamiento)

        data.append({
            'venta_reserva_id': servicio.venta_reserva.id,
            'cliente_nombre': servicio.venta_reserva.cliente.nombre,
            'categoria_servicio': servicio.servicio.categoria.nombre,
            'servicio_nombre': servicio.servicio.nombre,
            'fecha_agendamiento': fecha_agendamiento.date(),
            'hora_agendamiento': fecha_agendamiento.time(),
            'monto': servicio.servicio.precio_base,
            'cantidad_personas': servicio.cantidad_personas,
            'total_monto': total_monto
        })

    # Pasar los datos y las categorías a la plantilla
    context = {
        'servicios': data,
        'categorias': categorias,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'categoria_id': categoria_id,
        'venta_reserva_id': venta_reserva_id,
        'total_monto_vendido': total_monto_vendido
    }

    return render(request, 'ventas/servicios_vendidos.html', context)

class ProveedorViewSet(viewsets.ModelViewSet):
    queryset = Proveedor.objects.all()
    serializer_class = ProveedorSerializer


class CategoriaProductoViewSet(viewsets.ModelViewSet):
    queryset = CategoriaProducto.objects.all()
    serializer_class = CategoriaProductoSerializer


class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer


class ServicioViewSet(viewsets.ModelViewSet):
    queryset = Servicio.objects.all()
    serializer_class = ServicioSerializer


class CategoriaServicioViewSet(viewsets.ModelViewSet):
    queryset = CategoriaServicio.objects.all()
    serializer_class = CategoriaServicioSerializer


class ClienteViewSet(viewsets.ModelViewSet):
    queryset = Cliente.objects.all()
    serializer_class = ClienteSerializer


class ReservaProductoViewSet(viewsets.ModelViewSet):
    queryset = ReservaProducto.objects.all()
    serializer_class = ReservaProductoSerializer


class ReservaServicioViewSet(viewsets.ModelViewSet):
    queryset = ReservaServicio.objects.all()
    serializer_class = ReservaServicioSerializer

class VentaReservaViewSet(viewsets.ModelViewSet):
    queryset = VentaReserva.objects.all()
    serializer_class = VentaReservaSerializer

    def get_queryset(self):
        """
        Filtra las reservas por cliente, servicio, o fecha.
        """
        queryset = super().get_queryset()

        # Filtros por cliente, servicio y fecha
        cliente_id = self.request.query_params.get('cliente')
        servicio_id = self.request.query_params.get('servicio')
        fecha_inicio = self.request.query_params.get('fecha_inicio')
        fecha_fin = self.request.query_params.get('fecha_fin')

        # Filtrar por cliente
        if cliente_id:
            queryset = queryset.filter(cliente_id=cliente_id)

        # Filtrar por servicio
        if servicio_id:
            queryset = queryset.filter(servicios__id=servicio_id)

        # Filtrar por rango de fechas
        if fecha_inicio and fecha_fin:
            queryset = queryset.filter(fecha_reserva__range=[fecha_inicio, fecha_fin])
        elif fecha_inicio:
            queryset = queryset.filter(fecha_reserva__gte=fecha_inicio)
        elif fecha_fin:
            queryset = queryset.filter(fecha_reserva__lte=fecha_fin)

        return queryset

    def create(self, request, *args, **kwargs):
        data = request.data
        cliente_id = data.get('cliente')
        productos = data.get('productos')
        servicios = data.get('servicios')

        # Envolver en una transacción atómica
        with transaction.atomic():
            # Crear la venta/reserva
            venta_reserva = VentaReserva.objects.create(cliente_id=cliente_id)

            # Procesar los productos (sin lógica de reserva)
            for producto_data in productos:
                producto_id = producto_data.get('producto')
                cantidad = producto_data.get('cantidad')
                producto = Producto.objects.get(id=producto_id)

                # Verificar si hay inventario suficiente
                if producto.cantidad_disponible < cantidad:
                    raise ValidationError(f"No hay suficiente inventario para el producto {producto.nombre}.")

                # Reducir inventario y agregar producto a la reserva
                producto.reducir_inventario(cantidad)
                venta_reserva.agregar_producto(producto, cantidad)

            # Procesar los servicios (con lógica de reserva)
            for servicio_data in servicios:
                servicio_id = servicio_data.get('servicio')
                fecha_agendamiento = servicio_data.get('fecha_agendamiento')
                servicio = Servicio.objects.get(id=servicio_id)

                # Verificar disponibilidad del servicio
                if not verificar_disponibilidad(servicio, fecha_agendamiento, fecha_agendamiento + servicio.duracion):
                    raise ValidationError(f"El servicio {servicio.nombre} no está disponible en el horario solicitado.")

                # Agregar el servicio a la reserva
                venta_reserva.agregar_servicio(servicio, fecha_agendamiento)

            # Guardar la reserva y calcular el total
            venta_reserva.calcular_total()
            venta_reserva.save()

        # Serializar la respuesta con los datos actualizados
        serializer = self.get_serializer(venta_reserva)
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data

        # Procesar los productos actualizados (sin lógica de reserva)
        productos = data.get('productos', [])
        for producto_data in productos:
            producto_id = producto_data.get('producto')
            cantidad = producto_data.get('cantidad')
            producto = Producto.objects.get(id=producto_id)

            # Verificar si hay inventario suficiente antes de agregar
            if producto.cantidad_disponible < cantidad:
                raise ValidationError(f"No hay suficiente inventario para el producto {producto.nombre}.")

            instance.agregar_producto(producto, cantidad)

        # Procesar los servicios actualizados (con lógica de reserva)
        servicios = data.get('servicios', [])
        for servicio_data in servicios:
            servicio_id = servicio_data.get('servicio')
            fecha_agendamiento = servicio_data.get('fecha_agendamiento')
            servicio = Servicio.objects.get(id=servicio_id)

            # Verificar disponibilidad del servicio
            if not verificar_disponibilidad(servicio, fecha_agendamiento, fecha_agendamiento + servicio.duracion):
                raise ValidationError(f"El servicio {servicio.nombre} no está disponible en el horario solicitado.")

            instance.agregar_servicio(servicio, fecha_agendamiento)

        instance.save()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)
    
class PagoViewSet(viewsets.ModelViewSet):
    queryset = Pago.objects.all()
    serializer_class = PagoSerializer

    def create(self, request, *args, **kwargs):
        data = request.data
        venta_reserva_id = data.get('venta_reserva')
        monto = data.get('monto')
        metodo_pago = data.get('metodo_pago')

        venta_reserva = VentaReserva.objects.get(id=venta_reserva_id)

        pago = Pago.objects.create(
            venta_reserva=venta_reserva,
            monto=monto,
            metodo_pago=metodo_pago,
            fecha_pago=timezone.now()
        )

        venta_reserva.pagado += pago.monto
        venta_reserva.saldo_pendiente = venta_reserva.total - venta_reserva.pagado

        if venta_reserva.saldo_pendiente <= 0:
            venta_reserva.estado = 'pagado'
        elif 0 < venta_reserva.saldo_pendiente < venta_reserva.total:
            venta_reserva.estado = 'parcial'
        else:
            venta_reserva.estado = 'pendiente'

        venta_reserva.save()

        serializer = self.get_serializer(pago)
        return Response(serializer.data)

def inicio_sistema_view(request):
    """
    Vista que renderiza la página de inicio del sistema con enlaces a los recursos importantes.
    """
    return render(request, 'ventas/inicio_sistema.html')


# Función para verificar si el usuario es administrador
def es_administrador(user):
    return user.is_superuser

@user_passes_test(es_administrador)  # Restringir el acceso a administradores
def auditoria_movimientos_view(request):
    # Obtener los parámetros del filtro
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    cliente_id = request.GET.get('cliente')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    usuario_username = request.GET.get('usuario')  # Cambiar a username en lugar de id

    # Obtener todos los movimientos, pre-cargando datos del cliente y usuario
    movimientos = MovimientoCliente.objects.select_related('cliente', 'usuario').all()

    # Filtrar por cliente si se proporciona
    if cliente_id:
        movimientos = movimientos.filter(cliente_id=cliente_id)

    # Filtrar por rango de fechas si se proporciona
    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        movimientos = movimientos.filter(fecha_movimiento__gte=fecha_inicio)
    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d') + timedelta(days=1) - timedelta(seconds=1)
        movimientos = movimientos.filter(fecha_movimiento__lte=fecha_fin)

    # Filtrar por tipo de movimiento si se proporciona
    if tipo_movimiento and tipo_movimiento != 'None':
        movimientos = movimientos.filter(tipo_movimiento=tipo_movimiento)

    # Filtrar por usuario si se proporciona
    if usuario_username and usuario_username != 'None':
        movimientos = movimientos.filter(usuario__username=usuario_username)

    # Obtener todos los usuarios para la lista desplegable
    usuarios = User.objects.all()

    # Pasar los movimientos al contexto de la plantilla
    context = {
        'movimientos': movimientos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'cliente_id': cliente_id,
        'tipo_movimiento': tipo_movimiento if tipo_movimiento != 'None' else '',
        'usuario_username': usuario_username if usuario_username != 'None' else '',
        'usuarios': usuarios,  # Enviar los usuarios al contexto para la lista desplegable
    }

    return render(request, 'ventas/auditoria_movimientos.html', context)

@user_passes_test(es_administrador)  # Restringir el acceso a administradores
def caja_diaria_view(request):
    # Obtener rango de fechas desde los parámetros GET
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    metodo_pago = request.GET.get('metodo_pago')  # Nuevo filtro

    # Establecer fechas por defecto (hoy) si no se proporcionan
    today = timezone.localdate()
    if not fecha_inicio:
        fecha_inicio = today.strftime('%Y-%m-%d')
    if not fecha_fin:
        fecha_fin = today.strftime('%Y-%m-%d')

    # Parsear las cadenas de fecha a objetos date
    try:
        fecha_inicio_parsed = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin_parsed = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    except ValueError:
        # Manejar errores de formato de fecha
        fecha_inicio_parsed = today
        fecha_fin_parsed = today

    # Validar que fecha_inicio no es posterior a fecha_fin
    if fecha_inicio_parsed > fecha_fin_parsed:
        fecha_inicio_parsed, fecha_fin_parsed = fecha_fin_parsed, fecha_inicio_parsed
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    # Ajustar fecha_fin para incluir todo el día
    fecha_fin_parsed_datetime = timezone.make_aware(datetime.combine(fecha_fin_parsed, datetime.min.time())) + timedelta(days=1)

    # Obtener el usuario seleccionado del parámetro GET
    usuario_id = request.GET.get('usuario')

    # Obtener todos los usuarios para el filtro
    usuarios = User.objects.all()

    # Filtrar Pago basado en fecha_pago
    pagos = Pago.objects.filter(
        fecha_pago__range=(fecha_inicio_parsed, fecha_fin_parsed_datetime)
    )

    # Filtrar los pagos por usuario si se ha seleccionado uno
    if usuario_id:
        pagos = pagos.filter(usuario_id=usuario_id)
    else:
        usuario_id = ''

    # Filtrar por método de pago si se ha seleccionado uno
    if metodo_pago:
        pagos = pagos.filter(metodo_pago=metodo_pago)
    else:
        metodo_pago = ''

    # Filtrar VentaReserva basado en ReservaServicio.fecha_agendamiento
    ventas = VentaReserva.objects.filter(
        reservaservicios__fecha_agendamiento__range=(fecha_inicio_parsed, fecha_fin_parsed_datetime)
    ).distinct()

    # Calcular totales
    total_ventas = ventas.aggregate(total=Sum('total'))['total'] or 0
    total_pagos = pagos.aggregate(total=Sum('monto'))['total'] or 0

    # Agrupar pagos por método de pago y contar transacciones
    pagos_grouped = pagos.values('metodo_pago').annotate(
        total_monto=Sum('monto'),
        cantidad_transacciones=Count('id')
    ).order_by('metodo_pago')

    # Obtener los métodos de pago para el filtro
    METODOS_PAGO = Pago.METODOS_PAGO

    context = {
        'ventas': ventas,
        'pagos': pagos,
        'total_ventas': total_ventas,
        'total_pagos': total_pagos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'pagos_grouped': pagos_grouped,
        'usuarios': usuarios,
        'usuario_id': usuario_id,
        'metodo_pago': metodo_pago,  # Añadir al contexto
        'METODOS_PAGO': METODOS_PAGO,  # Añadir al contexto
    }

    return render(request, 'ventas/caja_diaria.html', context)

def caja_diaria_recepcionistas_view(request):
    # Lista de usuarios permitidos (por username)
    usuarios_permitidos_usernames = ['Lina', 'Edson', 'Ernesto', 'Rafael']
    usuarios_permitidos = User.objects.filter(username__in=usuarios_permitidos_usernames)

    # Obtener rango de fechas y filtros
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    metodo_pago = request.GET.get('metodo_pago')
    usuario_id = request.GET.get('usuario')

    # Establecer fechas por defecto
    today = timezone.localdate()
    if not fecha_inicio:
        fecha_inicio = today.strftime('%Y-%m-%d')
    if not fecha_fin:
        fecha_fin = today.strftime('%Y-%m-%d')

    # Parsear fechas
    try:
        fecha_inicio_parsed = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin_parsed = datetime.strptime(fecha_fin, '%Y-%m-%d').date()
    except ValueError:
        fecha_inicio_parsed = today
        fecha_fin_parsed = today

    # Validar fechas
    if fecha_inicio_parsed > fecha_fin_parsed:
        fecha_inicio_parsed, fecha_fin_parsed = fecha_fin_parsed, fecha_inicio_parsed
        fecha_inicio, fecha_fin = fecha_fin, fecha_inicio

    # Ajustar fecha_fin
    fecha_fin_parsed_datetime = timezone.make_aware(datetime.combine(fecha_fin_parsed, datetime.max.time()))

    # Filtrar pagos
    pagos = Pago.objects.filter(
        fecha_pago__range=(fecha_inicio_parsed, fecha_fin_parsed_datetime),
        usuario__in=usuarios_permitidos
    )

    if usuario_id:
        pagos = pagos.filter(usuario_id=usuario_id)

    if metodo_pago:
        pagos = pagos.filter(metodo_pago=metodo_pago)

    # Filtrar ventas basadas en pagos filtrados
    ventas = VentaReserva.objects.filter(
        pagos__in=pagos
    ).distinct()

    # Calcular totales
    total_ventas = ventas.aggregate(total=Sum('total'))['total'] or 0
    total_pagos = pagos.aggregate(total=Sum('monto'))['total'] or 0

    # Agrupar pagos
    pagos_grouped = pagos.values('metodo_pago').annotate(
        total_monto=Sum('monto'),
        cantidad_transacciones=Count('id')
    ).order_by('metodo_pago')

    # Contexto
    context = {
        'ventas': ventas,
        'pagos': pagos,
        'total_ventas': total_ventas,
        'total_pagos': total_pagos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'pagos_grouped': pagos_grouped,
        'usuarios': usuarios_permitidos,
        'usuario_id': usuario_id or '',
        'metodo_pago': metodo_pago or '',
        'METODOS_PAGO': Pago.METODOS_PAGO,
    }

    return render(request, 'ventas/caja_diaria_recepcionistas.html', context)

@login_required
def productos_vendidos(request):
    # Obtener fechas del request
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    proveedor_id = request.GET.get('proveedor')
    producto_id = request.GET.get('producto')

    # Establecer fechas por defecto si no se proporcionan
    if not fecha_inicio or not fecha_fin:
        fecha_actual = timezone.now().date()
        fecha_inicio = fecha_actual
        fecha_fin = fecha_actual
    else:
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d').date()
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d').date()

    # Construir la consulta base
    productos_query = ReservaProducto.objects.select_related(
        'venta_reserva',
        'venta_reserva__cliente',
        'producto',
        'producto__categoria'
    ).filter(
        venta_reserva__fecha_reserva__date__range=[fecha_inicio, fecha_fin],
        venta_reserva__isnull=False  # Asegurarse de que venta_reserva no sea null
    )

    # Aplicar filtros adicionales solo si se proporcionan valores válidos
    if proveedor_id and proveedor_id.isdigit():
        productos_query = productos_query.filter(producto__proveedor_id=int(proveedor_id))
    
    if producto_id and producto_id.isdigit():
        productos_query = productos_query.filter(producto_id=int(producto_id))

    # Obtener los resultados
    productos = productos_query.values(
        'venta_reserva_id',
        'venta_reserva__cliente__nombre',
        'producto__categoria__nombre',
        'producto__nombre',
        'cantidad',
        'producto__precio_base'
    ).annotate(
        total_monto=F('cantidad') * F('producto__precio_base')
    ).exclude(
        venta_reserva_id__isnull=True
    ).order_by('-venta_reserva__fecha_reserva')  # Ordenar por fecha de reserva descendente

    context = {
        'productos': productos,
        'proveedores': Proveedor.objects.all().order_by('nombre'),
        'productos': Producto.objects.all().order_by('nombre'),
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'proveedor_id': int(proveedor_id) if proveedor_id and proveedor_id.isdigit() else None,
        'producto_id': int(producto_id) if producto_id and producto_id.isdigit() else None,
    }

    return render(request, 'ventas/productos_vendidos.html', context)