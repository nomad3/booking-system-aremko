"""
Vista para gestión de inventario con comparación de stock actual vs día anterior
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import datetime, timedelta
from ..models import Producto, ReservaProducto

def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)

@staff_required
def gestion_inventario(request):
    """
    Vista principal de gestión de inventario.
    Muestra el stock actual y el stock al cierre del día anterior.
    """
    # Obtener fecha actual y fecha de ayer en zona horaria local
    ahora_local = timezone.localtime(timezone.now())
    hoy = ahora_local.date()
    ayer = hoy - timedelta(days=1)

    # Obtener todos los productos activos
    productos = Producto.objects.all().select_related('categoria', 'proveedor').order_by('nombre')

    # Modo debug (opcional)
    debug_mode = request.GET.get('debug', '').lower() == 'true'

    # Preparar datos de inventario
    inventario_data = []

    for producto in productos:
        # Stock actual del sistema
        stock_actual = producto.cantidad_disponible

        # Calcular productos vendidos hoy (con fecha_entrega = hoy o NULL con primer servicio = hoy)
        from django.db.models import Min

        # Caso 1: fecha_entrega explícita = hoy
        vendidos_con_fecha_explicita = ReservaProducto.objects.filter(
            producto=producto,
            fecha_entrega=hoy,
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).aggregate(
            total=Sum('cantidad')
        )['total'] or 0

        # Caso 2: fecha_entrega NULL y primer servicio de la reserva = hoy
        vendidos_con_fecha_null = ReservaProducto.objects.filter(
            producto=producto,
            fecha_entrega__isnull=True,
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).annotate(
            primer_servicio=Min('venta_reserva__reservaservicios__fecha_agendamiento')
        ).filter(
            primer_servicio=hoy
        ).aggregate(
            total=Sum('cantidad')
        )['total'] or 0

        productos_vendidos_hoy = vendidos_con_fecha_explicita + vendidos_con_fecha_null

        # Stock al cierre de ayer (stock actual + productos vendidos hoy)
        # Este es el stock que deberían tener físicamente si no se han entregado los productos de hoy
        stock_cierre_ayer = stock_actual + productos_vendidos_hoy

        # Calcular diferencia
        diferencia = stock_cierre_ayer - stock_actual

        # Info adicional de debug
        debug_info = None
        if debug_mode and productos_vendidos_hoy > 0:
            # Obtener detalles de las ventas de hoy
            reservas_hoy = ReservaProducto.objects.filter(
                producto=producto
            ).filter(
                Q(fecha_entrega=hoy) |
                (Q(fecha_entrega__isnull=True) & Q(venta_reserva__reservaservicios__fecha_agendamiento=hoy))
            ).exclude(
                venta_reserva__estado_reserva='cancelada'
            ).distinct().values(
                'venta_reserva__id',
                'cantidad',
                'fecha_entrega',
                'venta_reserva__estado_reserva'
            )
            debug_info = list(reservas_hoy)

        inventario_data.append({
            'producto': producto,
            'stock_actual': stock_actual,
            'stock_cierre_ayer': stock_cierre_ayer,
            'productos_vendidos_hoy': productos_vendidos_hoy,
            'diferencia': diferencia,
            'categoria': producto.categoria.nombre if producto.categoria else 'Sin categoría',
            'proveedor': producto.proveedor.nombre if producto.proveedor else 'Sin proveedor',
            'debug_info': debug_info
        })

    # Filtrar por categoría si se especifica
    categoria_filtro = request.GET.get('categoria', '')
    if categoria_filtro:
        inventario_data = [item for item in inventario_data if item['categoria'] == categoria_filtro]

    # Obtener lista de categorías para el filtro
    categorias = list(set([item['categoria'] for item in inventario_data]))
    categorias.sort()

    # Verificar si el usuario puede ajustar inventario
    usuarios_permitidos = ['alda', 'jorge', 'admin']
    puede_ajustar = request.user.username.lower() in usuarios_permitidos or request.user.is_superuser

    context = {
        'inventario_data': inventario_data,
        'fecha_actual': hoy.strftime('%d/%m/%Y'),
        'fecha_ayer': ayer.strftime('%d/%m/%Y'),
        'hora_actual': timezone.localtime(timezone.now()).strftime('%H:%M'),
        'categorias': categorias,
        'categoria_seleccionada': categoria_filtro,
        'total_productos': len(inventario_data),
        'debug_mode': debug_mode,
        'puede_ajustar': puede_ajustar,
        'usuario_actual': request.user.username
    }

    return render(request, 'ventas/inventario/gestion_inventario.html', context)

@staff_required
def ajustar_inventario(request, producto_id):
    """
    Vista para ajustar manualmente el inventario de un producto.
    Esta función permite corregir discrepancias entre inventario físico y del sistema.
    Solo permitida para usuarios específicos: alda, jorge, admin.
    """
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages
    from django.http import HttpResponseForbidden

    # Verificar permisos específicos
    usuarios_permitidos = ['alda', 'jorge', 'admin']
    if not (request.user.username.lower() in usuarios_permitidos or request.user.is_superuser):
        messages.error(request, 'No tienes permisos para ajustar inventario.')
        return HttpResponseForbidden('No tienes permisos para realizar esta acción.')

    if request.method == 'POST':
        producto = get_object_or_404(Producto, id=producto_id)

        try:
            nuevo_stock = int(request.POST.get('nuevo_stock', 0))
            motivo = request.POST.get('motivo', '')

            if nuevo_stock < 0:
                messages.error(request, 'El stock no puede ser negativo.')
            else:
                stock_anterior = producto.cantidad_disponible
                producto.cantidad_disponible = nuevo_stock
                producto.save()

                # TODO: Registrar el ajuste en un log de auditoría
                messages.success(
                    request,
                    f'Stock de {producto.nombre} ajustado de {stock_anterior} a {nuevo_stock}. '
                    f'Motivo: {motivo}'
                )
        except ValueError:
            messages.error(request, 'El valor ingresado no es válido.')

        return redirect('ventas:gestion_inventario')

    return redirect('ventas:gestion_inventario')