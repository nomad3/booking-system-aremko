"""
Vistas públicas para sistema de comandas de clientes vía WhatsApp
Los clientes acceden con un token único y pueden crear su propia comanda.
Flujo multi-pedido: el cliente puede hacer varios pedidos durante su estadía;
cada confirmación genera una comanda independiente para cocina y el pago se
consolida al checkout en recepción.
"""
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
import json
import logging

from ventas.models import Comanda, DetalleComanda, Producto, ReservaProducto

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_comanda_or_error(token):
    """Valida token y expiración.  Devuelve (comanda, error_response)."""
    comanda = Comanda.objects.filter(token_acceso=token).first()
    if not comanda:
        return None, JsonResponse({'success': False, 'error': 'Token inválido'}, status=404)
    if not comanda.es_link_valido():
        return None, None  # Expirado — el caller decide cómo responder
    return comanda, None


def _get_venta_reserva_from_token(token):
    """Encuentra la VentaReserva asociada al token (puede estar en comanda activa o en una ya confirmada)."""
    comanda = Comanda.objects.filter(token_acceso=token).select_related('venta_reserva').first()
    if comanda:
        return comanda.venta_reserva, comanda
    return None, None


# ---------------------------------------------------------------------------
# Vista principal: menú de productos + historial de pedidos
# ---------------------------------------------------------------------------

def comanda_cliente_menu(request, token):
    """
    Muestra el menú para un nuevo pedido y el historial de pedidos anteriores.
    El token siempre apunta a la comanda 'borrador' activa.
    """
    comanda = Comanda.objects.filter(token_acceso=token).select_related('venta_reserva__cliente').first()

    if not comanda:
        return render(request, 'ventas/comanda_cliente/error.html', {
            'error': 'token_invalido',
            'mensaje': 'Este link no es válido. Solicita uno nuevo al spa.',
        })

    if not comanda.es_link_valido():
        return render(request, 'ventas/comanda_cliente/error.html', {
            'error': 'link_expirado',
            'mensaje': 'Este link ha expirado. Por favor contacta al spa para solicitar uno nuevo.',
        })

    # Si la comanda con el token ya no está en borrador (edge case: recarga
    # tras confirmar antes de que se transfiera el token), buscar borrador activo.
    if comanda.estado != 'borrador':
        borrador = Comanda.objects.filter(
            venta_reserva=comanda.venta_reserva,
            creada_por_cliente=True,
            estado='borrador',
        ).first()
        if borrador:
            comanda = borrador
        else:
            # No hay borrador — no debería pasar, pero crear uno
            comanda = Comanda.objects.create(
                venta_reserva=comanda.venta_reserva,
                estado='borrador',
                creada_por_cliente=True,
                token_acceso=token,
                fecha_vencimiento_link=comanda.fecha_vencimiento_link,
                usuario_solicita=comanda.usuario_solicita,
            )

    # Productos disponibles
    productos = Producto.objects.filter(
        comanda_cliente=True,
        cantidad_disponible__gt=0,
    ).order_by('orden_comanda', 'nombre')

    # Carrito activo
    detalles_actuales = comanda.detalles.select_related('producto').all()
    subtotal = sum(d.subtotal for d in detalles_actuales)

    # Pedidos anteriores confirmados (para historial)
    pedidos_anteriores = (
        Comanda.objects.filter(
            venta_reserva=comanda.venta_reserva,
            creada_por_cliente=True,
            estado__in=['pendiente', 'procesando', 'entregada'],
        )
        .prefetch_related('detalles__producto')
        .order_by('-fecha_solicitud')
    )

    context = {
        'comanda': comanda,
        'productos': productos,
        'detalles': detalles_actuales,
        'subtotal': subtotal,
        'token': token,
        'vencimiento': comanda.fecha_vencimiento_link,
        'pedidos_anteriores': pedidos_anteriores,
        'cliente_nombre': comanda.venta_reserva.cliente.nombre if comanda.venta_reserva and comanda.venta_reserva.cliente else '',
    }

    return render(request, 'ventas/comanda_cliente/menu.html', context)


# ---------------------------------------------------------------------------
# AJAX: agregar producto al carrito
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@csrf_exempt
def comanda_cliente_agregar_producto(request, token):
    """Agregar un producto a la comanda del cliente (AJAX)."""
    try:
        comanda = get_object_or_404(Comanda, token_acceso=token)

        if not comanda.es_link_valido():
            return JsonResponse({'success': False, 'error': 'Link expirado'}, status=403)

        if comanda.estado != 'borrador':
            return JsonResponse({'success': False, 'error': 'Comanda no editable'}, status=403)

        data = json.loads(request.body)
        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))

        if cantidad < 1:
            return JsonResponse({'success': False, 'error': 'Cantidad inválida'}, status=400)

        producto = get_object_or_404(Producto, id=producto_id, comanda_cliente=True)

        if producto.cantidad_disponible < cantidad:
            return JsonResponse({
                'success': False,
                'error': f'Stock insuficiente. Disponible: {producto.cantidad_disponible}',
            }, status=400)

        with transaction.atomic():
            detalle, created = DetalleComanda.objects.get_or_create(
                comanda=comanda,
                producto=producto,
                defaults={
                    'cantidad': cantidad,
                    'precio_unitario': producto.precio_base,
                    'especificaciones': '',
                },
            )

            if not created:
                detalle.cantidad += cantidad
                detalle.save()

            subtotal = sum(d.subtotal for d in comanda.detalles.all())

        return JsonResponse({
            'success': True,
            'mensaje': f'{producto.nombre} agregado al pedido',
            'detalle_id': detalle.id,
            'cantidad_total': detalle.cantidad,
            'subtotal_item': float(detalle.subtotal),
            'subtotal_comanda': float(subtotal),
        })

    except Exception as e:
        logger.error(f"Error al agregar producto a comanda: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# AJAX: actualizar cantidad de un producto
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@csrf_exempt
def comanda_cliente_actualizar_cantidad(request, token):
    """Actualizar la cantidad de un producto en la comanda (AJAX)."""
    try:
        comanda = get_object_or_404(Comanda, token_acceso=token)

        if not comanda.es_link_valido():
            return JsonResponse({'success': False, 'error': 'Link expirado'}, status=403)

        data = json.loads(request.body)
        detalle_id = data.get('detalle_id')
        cantidad = int(data.get('cantidad', 0))

        detalle = get_object_or_404(DetalleComanda, id=detalle_id, comanda=comanda)

        with transaction.atomic():
            if cantidad <= 0:
                detalle.delete()
                mensaje = 'Producto eliminado del pedido'
            else:
                if detalle.producto.cantidad_disponible < cantidad:
                    return JsonResponse({
                        'success': False,
                        'error': f'Stock insuficiente. Disponible: {detalle.producto.cantidad_disponible}',
                    }, status=400)
                detalle.cantidad = cantidad
                detalle.save()
                mensaje = 'Cantidad actualizada'

            subtotal = sum(d.subtotal for d in comanda.detalles.all())

        return JsonResponse({
            'success': True,
            'mensaje': mensaje,
            'subtotal_item': float(detalle.subtotal) if cantidad > 0 else 0,
            'subtotal_comanda': float(subtotal),
        })

    except Exception as e:
        logger.error(f"Error al actualizar cantidad: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# AJAX: confirmar pedido (enviar a cocina, sin pago)
# ---------------------------------------------------------------------------

@require_http_methods(["POST"])
@csrf_exempt
def comanda_cliente_finalizar(request, token):
    """
    Confirma el pedido: marca la comanda como 'pendiente' (cocina), crea los
    ReservaProducto para facturación, y genera una nueva comanda 'borrador'
    con el mismo token para que el cliente pueda hacer otro pedido.
    """
    try:
        comanda = get_object_or_404(Comanda, token_acceso=token)

        if not comanda.es_link_valido():
            return JsonResponse({'success': False, 'error': 'Link expirado'}, status=403)

        if comanda.estado != 'borrador':
            return JsonResponse({'success': False, 'error': 'Este pedido ya fue confirmado'}, status=400)

        if not comanda.detalles.exists():
            return JsonResponse({
                'success': False,
                'error': 'Agrega al menos un producto al pedido',
            }, status=400)

        with transaction.atomic():
            # 1. Crear ReservaProducto para cada detalle (para facturación al checkout)
            for detalle in comanda.detalles.select_related('producto').all():
                ReservaProducto.objects.create(
                    venta_reserva=comanda.venta_reserva,
                    producto=detalle.producto,
                    cantidad=detalle.cantidad,
                    precio_unitario_venta=detalle.precio_unitario,
                )

            # 2. Marcar comanda como pendiente (entra al flujo de cocina)
            saved_token = comanda.token_acceso
            saved_vencimiento = comanda.fecha_vencimiento_link
            saved_usuario = comanda.usuario_solicita

            comanda.estado = 'pendiente'
            comanda.token_acceso = None  # Liberar token
            comanda.save()

            # 3. Crear nueva comanda borrador con el mismo token (para siguiente pedido)
            Comanda.objects.create(
                venta_reserva=comanda.venta_reserva,
                estado='borrador',
                creada_por_cliente=True,
                token_acceso=saved_token,
                fecha_vencimiento_link=saved_vencimiento,
                usuario_solicita=saved_usuario,
            )

        # Resumen del pedido confirmado
        items = [
            {'nombre': d.producto.nombre, 'cantidad': d.cantidad, 'subtotal': float(d.subtotal)}
            for d in comanda.detalles.select_related('producto').all()
        ]
        total = sum(i['subtotal'] for i in items)

        return JsonResponse({
            'success': True,
            'pedido_id': comanda.id,
            'mensaje': f'Pedido #{comanda.id} enviado a cocina',
            'items': items,
            'total': total,
        })

    except Exception as e:
        logger.error(f"Error al confirmar pedido: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


# ---------------------------------------------------------------------------
# Vistas de pago (legacy, mantenidas por compatibilidad de URLs)
# ---------------------------------------------------------------------------

@csrf_exempt
def comanda_cliente_pago_confirmacion(request, token):
    """Webhook de pago (legacy — ya no se usa, se mantiene para evitar 404)."""
    return JsonResponse({'status': 'deprecated'}, status=410)


def comanda_cliente_pago_retorno(request, token):
    """Página de retorno de pago (legacy)."""
    return JsonResponse({'status': 'deprecated'}, status=410)
