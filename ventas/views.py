from rest_framework import viewsets
from rest_framework.response import Response
from django.db.models import Sum, Q, Count, F
from django.contrib.auth.decorators import user_passes_test
import csv
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from datetime import datetime, timedelta
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import Proveedor, CategoriaProducto, Producto, VentaReserva, ReservaProducto, Cliente, Pago, CategoriaServicio, Servicio, ReservaServicio, MovimientoCliente, Compra, DetalleCompra
from .signals import get_or_create_system_user
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
import xlwt
from django.core.paginator import Paginator
from openpyxl import load_workbook
from django.contrib import messages
from itertools import islice
from django.views.decorators.csrf import csrf_protect
import traceback # Import traceback for detailed error logging


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

    # Keep fecha_inicio and fecha_fin as date objects for filtering DateField

    # Consultar todos los servicios vendidos
    servicios_vendidos = ReservaServicio.objects.select_related('venta_reserva__cliente', 'servicio__categoria')

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

    # Ordenar los servicios vendidos (simplificado)
    servicios_vendidos = servicios_vendidos.order_by('-fecha_agendamiento')

    # Obtener todas las categorías de servicio para el filtro
    categorias = CategoriaServicio.objects.all()

    # Sumar el monto total de todos los servicios vendidos que se están mostrando
    total_monto_vendido = sum(servicio.servicio.precio_base * servicio.cantidad_personas for servicio in servicios_vendidos)

    # Preparar los datos para la tabla
    data = []
    for servicio in servicios_vendidos:
        total_monto = servicio.servicio.precio_base * servicio.cantidad_personas
        
        # Use the date directly from the DateField
        fecha_display = servicio.fecha_agendamiento
        
        # Try to parse the time string, otherwise use the string
        try:
            # Ensure hora_inicio is a string before parsing
            hora_inicio_str = str(servicio.hora_inicio) if servicio.hora_inicio is not None else ''
            hora_display = datetime.strptime(hora_inicio_str, '%H:%M').time()
        except (ValueError, TypeError):
            hora_display = servicio.hora_inicio # Fallback to original string if parsing fails or input is invalid

        data.append({
            'venta_reserva_id': servicio.venta_reserva.id,
            'cliente_nombre': servicio.venta_reserva.cliente.nombre,
            'categoria_servicio': servicio.servicio.categoria.nombre,
            'servicio_nombre': servicio.servicio.nombre,
            'fecha_agendamiento': fecha_display, # Use processed date
            'hora_agendamiento': hora_display,   # Use processed time
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
            'Monto Total'
        ]

        for col, header in enumerate(headers):
            ws.write(0, col, header, header_style)
            ws.col(col).width = 256 * 20  # Ancho aproximado de 20 caracteres

        # Datos
        for row, servicio in enumerate(data, 1):
            ws.write(row, 0, servicio['venta_reserva_id'])
            ws.write(row, 1, servicio['cliente_nombre'])
            ws.write(row, 2, servicio['categoria_servicio'])
            ws.write(row, 3, servicio['servicio_nombre'])
            
            # Convertir fecha y hora a objetos datetime si son strings
            fecha = servicio['fecha_agendamiento']
            if isinstance(fecha, str):
                fecha = datetime.strptime(fecha, '%Y-%m-%d').date()
            ws.write(row, 4, fecha, date_style)
            
            hora = servicio['hora_agendamiento']
            if isinstance(hora, str):
                hora = datetime.strptime(hora, '%H:%M').time()
            ws.write(row, 5, hora, time_style)
            
            ws.write(row, 6, servicio['cantidad_personas'])
            ws.write(row, 7, servicio['total_monto'], money_style)

        wb.save(response)
        return response

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

def homepage_view(request):
    """
    Vista que renderiza la página de inicio pública de Aremko.cl
    Muestra los servicios disponibles y permite realizar reservas.
    """
    # Obtener servicios activos
    servicios = Servicio.objects.filter(activo=True).select_related('categoria')
    categorias = CategoriaServicio.objects.all()
    
    # Obtener carrito de compras de la sesión o crear uno nuevo
    cart = request.session.get('cart', {'servicios': [], 'total': 0})
    
    context = {
        'servicios': servicios,
        'categorias': categorias,
        'cart': cart
    }
    return render(request, 'ventas/homepage.html', context)

def cart_view(request):
    """
    Vista que renderiza la página del carrito de compras
    """
    # Obtener carrito de compras de la sesión o crear uno nuevo
    cart = request.session.get('cart', {'servicios': [], 'total': 0})
    
    context = {
        'cart': cart
    }
    return render(request, 'ventas/cart.html', context)

def add_to_cart(request):
    """
    Vista para agregar un servicio al carrito de compras
    """
    if request.method == 'POST':
        servicio_id = request.POST.get('servicio_id')
        fecha = request.POST.get('fecha')
        hora = request.POST.get('hora')
        cantidad_personas = int(request.POST.get('cantidad_personas', 1))
        
        print(f"Adding to cart: servicio_id={servicio_id}, fecha={fecha}, hora={hora}, cantidad_personas={cantidad_personas}")
        
        try:
            servicio = Servicio.objects.get(id=servicio_id)
            
            # Obtener carrito actual o crear uno nuevo
            cart = request.session.get('cart', {'servicios': [], 'total': 0})
            
            # Agregar servicio al carrito
            item = {
                'id': servicio.id,  # Use 'id' consistently
                'nombre': servicio.nombre,
                'precio': float(servicio.precio_base),
                'fecha': fecha,
                'hora': hora,
                'cantidad_personas': cantidad_personas,
                'subtotal': float(servicio.precio_base) * cantidad_personas
            }
            
            print(f"Cart item to add: {item}")
            
            cart['servicios'].append(item)
            
            # Recalcular total
            cart['total'] = sum(item['subtotal'] for item in cart['servicios'])
            
            # Guardar carrito en la sesión
            request.session['cart'] = cart
            request.session.modified = True
            
            print(f"Updated cart: {cart}")
            
            # Redirigir a la página de checkout en lugar de la página del carrito
            return redirect('checkout')
        except Servicio.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Servicio no encontrado'})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def remove_from_cart(request):
    if request.method == 'POST':
        try:
            index = int(request.POST.get('index', ''))
            cart = request.session.get('cart', {'servicios': [], 'total': 0})
            found = False  # Initialize found variable
            
            if 'servicios' in cart:
                for i, item in enumerate(cart['servicios']):
                    if i == index:
                        service_id = item.get('id')
                        del cart['servicios'][i]
                        found = True
                        break
            
            # Recalculate total
            total = 0
            for item in cart.get('servicios', []):
                total += float(item.get('subtotal', 0))
            
            cart['total'] = total
            
            request.session['cart'] = cart
            request.session.modified = True
            
            return JsonResponse({'success': True})
        except Exception as e:
            import traceback
            print("Error removing from cart:", str(e))
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': f'Error interno del servidor: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def checkout_view(request):
    # Get cart from session
    cart = request.session.get('cart', {'servicios': [], 'total': 0})
    
    context = {
        'cart': cart,
    }
    
    return render(request, 'ventas/checkout.html', context)

def complete_checkout(request):
    if request.method == 'POST':
        try:
            # Get form data
            nombre = request.POST.get('nombre')
            email = request.POST.get('email')
            telefono = request.POST.get('telefono')
            documento_identidad = request.POST.get('documento_identidad', '')
            
            # Get cart from session
            cart = request.session.get('cart', {'servicios': [], 'total': 0})
            
            # Debug cart structure
            print("CART STRUCTURE:")
            print(f"Cart type: {type(cart)}")
            print(f"Cart keys: {cart.keys()}")
            print(f"Cart servicios: {cart.get('servicios', [])}")
            
            if not cart.get('servicios'):
                return JsonResponse({'success': False, 'error': 'El carrito está vacío'})
            
            # Create cliente if it doesn't exist
            cliente, created = Cliente.objects.get_or_create(
                email=email,
                defaults={
                    'nombre': nombre,
                    'telefono': telefono,
                    'documento_identidad': documento_identidad
                }
            )
            
            # If cliente exists but we have new info, update it
            if not created:
                cliente.nombre = nombre
                cliente.telefono = telefono
                if documento_identidad:
                    cliente.documento_identidad = documento_identidad
                cliente.save()
            
            # Create VentaReserva
            with transaction.atomic():
                venta = VentaReserva.objects.create(
                    cliente=cliente,
                    total=cart['total'],
                    estado_pago='pendiente',
                    estado_reserva='pendiente',
                    fecha_reserva=timezone.now()
                )
                
                # Create ReservaServicio for each service in cart
                for servicio in cart['servicios']:
                    # Get the service ID
                    servicio_id = servicio.get('id')
                    
                    if not servicio_id:
                        print(f"Warning: Missing service ID in cart item: {servicio}")
                        continue
                    
                    servicio_obj = Servicio.objects.get(id=servicio_id)
                    fecha = datetime.strptime(servicio['fecha'], '%Y-%m-%d').date()
                    
                    ReservaServicio.objects.create(
                        venta_reserva=venta,
                        servicio=servicio_obj,
                        fecha_agendamiento=fecha,
                        hora_inicio=servicio['hora'],
                        cantidad_personas=servicio['cantidad_personas']
                    )
                
                # Recalculate total based on the services added
                venta.calcular_total()
                venta.save()
                
                # Clear cart
                request.session['cart'] = {'servicios': [], 'total': 0}
                request.session.modified = True
                
                # Return success response
                return JsonResponse({
                    'success': True, 
                    'message': 'Reserva creada exitosamente',
                    'reserva_id': venta.id
                })
        
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    # If not POST, return error as JSON
    return JsonResponse({'success': False, 'error': 'Método no permitido'})

def get_available_hours(request):
    """
    Vista para obtener las horas disponibles para un servicio en una fecha específica
    """
    servicio_id = request.GET.get('servicio_id')
    fecha = request.GET.get('fecha')
    
    try:
        servicio = Servicio.objects.get(id=servicio_id)
        fecha_obj = datetime.strptime(fecha, '%Y-%m-%d').date()
        
        # Obtener reservas existentes para este servicio en esta fecha
        # Convertir fecha_obj a string para comparar con el campo fecha_agendamiento
        reservas = ReservaServicio.objects.filter(
            servicio=servicio,
            fecha_agendamiento=fecha_obj
        ).values_list('hora_inicio', flat=True)
        
        # Si el servicio no tiene slots_disponibles definidos, crear algunos por defecto
        if not servicio.slots_disponibles or len(servicio.slots_disponibles) == 0:
            # Generar slots de hora en hora desde horario_apertura hasta horario_cierre
            hora_apertura = servicio.horario_apertura.hour
            hora_cierre = servicio.horario_cierre.hour
            
            # Si la hora de cierre es 0 (medianoche), ajustar a 24 para el cálculo
            if hora_cierre == 0:
                hora_cierre = 24
                
            slots_por_defecto = []
            for hora in range(hora_apertura, hora_cierre):
                slots_por_defecto.append(f"{hora:02d}:00")
                # También agregar slots de media hora si hay suficiente espacio
                if hora < hora_cierre - 1 or (hora == hora_cierre - 1 and servicio.duracion <= 30):
                    slots_por_defecto.append(f"{hora:02d}:30")
            
            # Actualizar el servicio con los slots generados
            servicio.slots_disponibles = slots_por_defecto
            servicio.save()
        
        # Obtener horas disponibles (slots_disponibles menos las horas ya reservadas)
        horas_disponibles = [hora for hora in servicio.slots_disponibles if hora not in reservas]
        
        # Ordenar las horas disponibles
        horas_disponibles.sort()
        
        # Agregar horas de prueba si no hay horas disponibles (para desarrollo)
        if not horas_disponibles:
            horas_disponibles = ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00", "18:00"]
        
        return JsonResponse({'success': True, 'horas_disponibles': horas_disponibles})
    except Servicio.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Servicio no encontrado'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Error de formato: {str(e)}'})
    except Exception as e:
        print(f"Error en get_available_hours: {str(e)}")
        return JsonResponse({'success': False, 'error': f'Error: {str(e)}'})


# Función para verificar si el usuario es administrador
def es_administrador(user):
    return user.is_staff or user.is_superuser

@user_passes_test(es_administrador)  # Restringir el acceso a administradores
def auditoria_movimientos_view(request):
    # Obtener parámetros del filtro
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')
    tipo_movimiento = request.GET.get('tipo_movimiento')
    usuario = request.GET.get('usuario')

    # Establecer fechas por defecto si no se proporcionan
    if not fecha_inicio:
        fecha_inicio = timezone.now().date().strftime('%Y-%m-%d')
    if not fecha_fin:
        fecha_fin = timezone.now().date().strftime('%Y-%m-%d')

    # Convertir fechas a objetos datetime
    fecha_inicio_dt = timezone.make_aware(datetime.strptime(fecha_inicio, '%Y-%m-%d'))
    fecha_fin_dt = timezone.make_aware(datetime.strptime(fecha_fin, '%Y-%m-%d')) + timedelta(days=1)

    # Iniciar el queryset base
    movimientos = MovimientoCliente.objects.select_related(
        'cliente', 'usuario', 'venta_reserva'
    )

    # Aplicar filtros
    movimientos = movimientos.filter(
        fecha_movimiento__gte=fecha_inicio_dt,
        fecha_movimiento__lte=fecha_fin_dt
    )

    if tipo_movimiento:
        movimientos = movimientos.filter(tipo_movimiento__icontains=tipo_movimiento)
    
    # Filtro de usuario mejorado
    if usuario and usuario != '':
        movimientos = movimientos.filter(usuario__username__exact=usuario)

    # Ordenar por fecha descendente
    movimientos = movimientos.order_by('-fecha_movimiento')

    # Agregar print para depuración
    print(f"Usuario seleccionado: {usuario}")
    print(f"Query SQL: {movimientos.query}")
    print(f"Cantidad de resultados: {movimientos.count()}")

    # Paginación
    paginator = Paginator(movimientos, 100)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'movimientos': page_obj,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'tipo_movimiento': tipo_movimiento,
        'usuario_username': usuario,
        'usuarios': User.objects.filter(is_active=True).order_by('username'),  # Solo usuarios activos
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
        venta_reserva__fecha_reserva__date__range=[fecha_inicio, fecha_fin]
    )

    # Aplicar filtros adicionales solo si se proporcionan valores válidos
    if proveedor_id and proveedor_id.strip():
        productos_query = productos_query.filter(producto__proveedor_id=proveedor_id)
    
    if producto_id and producto_id.strip():
        productos_query = productos_query.filter(producto_id=producto_id)

    # Calcular totales
    totales = productos_query.aggregate(
        total_cantidad_productos=Sum('cantidad'),
        total_monto_periodo=Sum(F('cantidad') * F('producto__precio_base'))
    )

    # Obtener los resultados
    productos = productos_query.values(
        'venta_reserva_id',
        'venta_reserva__cliente__nombre',
        'venta_reserva__fecha_reserva',
        'producto__proveedor__nombre',
        'producto__nombre',
        'cantidad',
        'producto__precio_base'
    ).annotate(
        total_monto=F('cantidad') * F('producto__precio_base')
    ).order_by('-venta_reserva__fecha_reserva')

    # Obtener listas para los filtros
    todos_proveedores = Proveedor.objects.all().order_by('nombre')
    todos_productos = Producto.objects.all().order_by('nombre')

    context = {
        'productos': productos,
        'proveedores': todos_proveedores,
        'productos_lista': todos_productos,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
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

        # Datos
        for row, producto in enumerate(productos, 1):
            monto_total = producto['cantidad'] * producto['producto__precio_base']
            
            # Convertir la fecha a zona horaria local
            fecha_venta = timezone.localtime(producto['venta_reserva__fecha_reserva'])
            
            ws.write(row, 0, producto['venta_reserva_id'] or 'Sin ID')
            ws.write(row, 1, producto['venta_reserva__cliente__nombre'])
            ws.write(row, 2, fecha_venta.strftime('%Y-%m-%d %H:%M'))  # Convertir a string
            ws.write(row, 3, producto['producto__proveedor__nombre'])
            ws.write(row, 4, producto['producto__nombre'])
            ws.write(row, 5, producto['cantidad'])
            ws.write(row, 6, producto['producto__precio_base'], money_style)
            ws.write(row, 7, monto_total, money_style)

        wb.save(response)
        return response

    return render(request, 'ventas/productos_vendidos.html', context)

@login_required
def exportar_clientes_excel(request):
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = 'attachment; filename="Clientes_{}.xls"'.format(
        datetime.now().strftime('%Y%m%d_%H%M%S')
    )

    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet('Clientes')

    # Estilos
    header_style = xlwt.easyxf('font: bold on; pattern: pattern solid, fore_colour gray25;')

    # Headers
    headers = ['ID', 'Nombre', 'Teléfono', 'Email']
    for col, header in enumerate(headers):
        ws.write(0, col, header, header_style)
        ws.col(col).width = 256 * 20

    # Obtener todos los clientes
    clientes = Cliente.objects.all().order_by('nombre')

    # Datos
    for row, cliente in enumerate(clientes, 1):
        ws.write(row, 0, cliente.id)
        ws.write(row, 1, cliente.nombre)
        ws.write(row, 2, cliente.telefono or '')
        ws.write(row, 3, cliente.email or '')

    wb.save(response)
    return response

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

@login_required
@user_passes_test(es_administrador)  # Solo administradores pueden importar
def importar_clientes_excel(request):
    BATCH_SIZE = 500
    
    if request.method == 'POST' and request.FILES.get('archivo_excel'):
        try:
            archivo = request.FILES['archivo_excel']
            wb = load_workbook(archivo)
            ws = wb.active
            
            clientes_nuevos = []
            clientes_actualizados = []
            errores = []
            total_procesados = 0
            batch_data = []
            
            for row in ws.iter_rows(min_row=2):
                try:
                    # Obtener valores (permitiendo valores vacíos)
                    documento_identidad = row[0].value if row[0].value is not None else ''
                    nombre = row[1].value if row[1].value is not None else ''
                    telefono = row[2].value if row[2].value is not None else ''
                    email = row[3].value if row[3].value is not None else ''
                    ciudad = row[4].value if len(row) > 4 and row[4].value else ''
                    
                    # Solo validar que el nombre no esté vacío
                    if not str(nombre).strip():
                        continue

                    # Agregar datos al lote
                    batch_data.append({
                        'row': row[0].row,
                        'documento_identidad': documento_identidad,  # Cambiado de identificacion
                        'nombre': nombre,
                        'telefono': telefono,
                        'email': email,
                        'ciudad': ciudad
                    })
                    
                    if len(batch_data) >= BATCH_SIZE:
                        process_batch(batch_data, clientes_nuevos, clientes_actualizados, errores)
                        total_procesados += len(batch_data)
                        messages.info(request, f'Procesados {total_procesados} registros...')
                        batch_data = []
                        
                except Exception as e:
                    errores.append(f"Error en fila {row[0].row}: {str(e)}")
            
            # Procesar el último lote
            if batch_data:
                process_batch(batch_data, clientes_nuevos, clientes_actualizados, errores)
                total_procesados += len(batch_data)
            
            # Mostrar resultados
            if clientes_nuevos:
                messages.success(request, f'Se importaron {len(clientes_nuevos)} nuevos clientes.')
            if clientes_actualizados:
                messages.info(request, f'Se actualizaron {len(clientes_actualizados)} clientes existentes.')
            if errores:
                messages.warning(request, f'Hubo {len(errores)} errores durante la importación.')
                for error in errores[:10]:
                    messages.error(request, error)
                if len(errores) > 10:
                    messages.error(request, f'... y {len(errores) - 10} errores más.')
                
        except Exception as e:
            messages.error(request, f'Error al procesar el archivo: {str(e)}')
            
    return render(request, 'ventas/importar_clientes.html')

def process_batch(batch_data, clientes_nuevos, clientes_actualizados, errores):
    """Procesa un lote de datos de clientes."""
    def limpiar_telefono(telefono):
        """Limpia y formatea el número telefónico."""
        try:
            if telefono is None:
                return ''
                
            telefono = str(telefono)
            solo_numeros = ''.join(filter(str.isdigit, telefono.strip()))
            
            if not solo_numeros:
                return ''
            
            return solo_numeros[-9:] if len(solo_numeros) >= 9 else solo_numeros
            
        except Exception:
            return ''

    def limpiar_email(email):
        """Limpia y valida el email."""
        if not email:
            return ''
        if str(email).strip().lower() == 'email':
            return ''
        email = str(email).strip()
        return email if '@' in email else ''

    # Set para mantener registro de documentos y teléfonos ya procesados
    documentos_procesados = set()
    telefonos_procesados = set()
    emails_procesados = set()

    with transaction.atomic():
        for data in batch_data:
            try:
                # Limpiar datos
                documento = str(data.get('documento_identidad', '')).strip()
                nombre = str(data.get('nombre', '')).strip()
                telefono = limpiar_telefono(data.get('telefono', ''))
                email = limpiar_email(data.get('email', ''))
                ciudad = str(data.get('ciudad', '')).strip()

                # Verificar duplicados
                if documento and documento in documentos_procesados:
                    continue
                if telefono and telefono in telefonos_procesados:
                    continue
                if email and email in emails_procesados:
                    continue

                # Buscar cliente existente
                criterios_busqueda = Q()
                if documento:
                    criterios_busqueda |= Q(documento_identidad=documento)
                if telefono:
                    criterios_busqueda |= Q(telefono=telefono)
                if email:
                    criterios_busqueda |= Q(email=email)

                cliente_existente = Cliente.objects.filter(criterios_busqueda).first() if criterios_busqueda else None

                if cliente_existente:
                    # Actualizar cliente existente
                    if documento:
                        cliente_existente.documento_identidad = documento
                    cliente_existente.nombre = nombre
                    if telefono:
                        cliente_existente.telefono = telefono
                    if email:
                        cliente_existente.email = email
                    if ciudad:
                        cliente_existente.ciudad = ciudad
                    cliente_existente.save()
                    clientes_actualizados.append(f"{nombre} (fila {data['row']})")
                else:
                    # Crear nuevo cliente
                    nuevo_cliente = {
                        'documento_identidad': documento,
                        'nombre': nombre,
                        'telefono': telefono,
                        'email': email,
                        'ciudad': ciudad
                    }
                    cliente = Cliente.objects.create(**nuevo_cliente)
                    clientes_nuevos.append(f"{nombre} (fila {data['row']})")

                # Registrar datos procesados
                if documento:
                    documentos_procesados.add(documento)
                if telefono:
                    telefonos_procesados.add(telefono)
                if email:
                    emails_procesados.add(email)

            except Exception as e:
                errores.append(f"Error en fila {data['row']}: Error al guardar en la base de datos: {str(e)}")

@login_required
def add_venta_reserva(request):
    if request.method == 'POST':
        try:
            form = VentaReservaForm(request.POST)
            if form.is_valid():
                venta_reserva = form.save(commit=False)
                venta_reserva.usuario = request.user
                venta_reserva.save()
                form.save_m2m()

                # Crear movimiento del cliente usando los campos correctos
                MovimientoCliente.objects.create(
                    cliente=venta_reserva.cliente,
                    monto=venta_reserva.total,
                    tipo_movimiento='Venta',
                    comentarios=f'Venta/Reserva #{venta_reserva.id}',
                    usuario=request.user
                )

                messages.success(request, 'Venta/Reserva creada exitosamente.')
                if 'guardar_y_agregar' in request.POST:
                    return redirect('admin:ventas_ventareserva_add')
                else:
                    return redirect('admin:ventas_ventareserva_changelist')
            else:
                messages.error(request, 'Por favor corrija los errores en el formulario.')
        except Exception as e:
            messages.error(request, f'Error al crear la venta/reserva: {str(e)}')
            return redirect('admin:ventas_ventareserva_add')

    return render(request, 'admin/ventas/ventareserva/change_form.html', {
        'form': VentaReservaForm(),
        'title': 'Agregar Venta/Reserva',
    })
