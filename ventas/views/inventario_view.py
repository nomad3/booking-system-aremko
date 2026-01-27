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
    # Obtener fecha actual y fecha de ayer
    hoy = timezone.now().date()
    ayer = hoy - timedelta(days=1)

    # Obtener todos los productos activos
    productos = Producto.objects.all().select_related('categoria', 'proveedor').order_by('nombre')

    # Preparar datos de inventario
    inventario_data = []

    for producto in productos:
        # Stock actual del sistema
        stock_actual = producto.cantidad_disponible

        # Calcular productos vendidos hoy (con fecha_entrega = hoy)
        productos_vendidos_hoy = ReservaProducto.objects.filter(
            producto=producto,
            fecha_entrega=hoy,
            venta_reserva__estado_reserva__in=['confirmada', 'en_proceso']
        ).aggregate(
            total=Sum('cantidad')
        )['total'] or 0

        # Stock al cierre de ayer (stock actual + productos vendidos hoy)
        # Este es el stock que deberían tener físicamente si no se han entregado los productos de hoy
        stock_cierre_ayer = stock_actual + productos_vendidos_hoy

        # Calcular diferencia
        diferencia = stock_cierre_ayer - stock_actual

        inventario_data.append({
            'producto': producto,
            'stock_actual': stock_actual,
            'stock_cierre_ayer': stock_cierre_ayer,
            'productos_vendidos_hoy': productos_vendidos_hoy,
            'diferencia': diferencia,
            'categoria': producto.categoria.nombre if producto.categoria else 'Sin categoría',
            'proveedor': producto.proveedor.nombre if producto.proveedor else 'Sin proveedor'
        })

    # Filtrar por categoría si se especifica
    categoria_filtro = request.GET.get('categoria', '')
    if categoria_filtro:
        inventario_data = [item for item in inventario_data if item['categoria'] == categoria_filtro]

    # Obtener lista de categorías para el filtro
    categorias = list(set([item['categoria'] for item in inventario_data]))
    categorias.sort()

    context = {
        'inventario_data': inventario_data,
        'fecha_actual': hoy.strftime('%d/%m/%Y'),
        'fecha_ayer': ayer.strftime('%d/%m/%Y'),
        'hora_actual': timezone.now().strftime('%H:%M'),
        'categorias': categorias,
        'categoria_seleccionada': categoria_filtro,
        'total_productos': len(inventario_data)
    }

    return render(request, 'ventas/inventario/gestion_inventario.html', context)

@staff_required
def ajustar_inventario(request, producto_id):
    """
    Vista para ajustar manualmente el inventario de un producto.
    Esta función permite corregir discrepancias entre inventario físico y del sistema.
    """
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib import messages

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