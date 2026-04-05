"""
Vistas públicas para sistema de comandas de clientes vía WhatsApp
Los clientes acceden con un token único y pueden crear su propia comanda
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from decimal import Decimal
import json
import logging

from ventas.models import Comanda, DetalleComanda, Producto, VentaReserva
from ventas.services.flow_service import FlowService

logger = logging.getLogger(__name__)


def comanda_cliente_menu(request, token):
    """
    Vista principal del menú de productos para el cliente
    Acceso mediante token único enviado por WhatsApp
    """
    # Validar token y obtener comanda
    comanda = get_object_or_404(Comanda, token_acceso=token)

    # Verificar que el link no haya expirado
    if not comanda.es_link_valido():
        context = {
            'error': 'link_expirado',
            'mensaje': 'Este link ha expirado. Por favor contacta al spa para solicitar uno nuevo.'
        }
        return render(request, 'ventas/comanda_cliente/error.html', context)

    # Verificar que la comanda esté en estado válido para edición
    estados_validos = ['borrador', 'pendiente_pago']
    if comanda.estado not in estados_validos:
        context = {
            'error': 'comanda_no_editable',
            'mensaje': 'Esta comanda ya ha sido procesada y no puede ser modificada.'
        }
        return render(request, 'ventas/comanda_cliente/error.html', context)

    # Obtener productos disponibles para comandas de clientes
    productos = Producto.objects.filter(
        comanda_cliente=True,
        activo=True,
        stock__gt=0
    ).order_by('orden_comanda', 'nombre')

    # Obtener detalles actuales de la comanda (si existen)
    detalles_actuales = comanda.detalles.all()

    # Calcular totales
    subtotal = sum(det.subtotal for det in detalles_actuales)

    context = {
        'comanda': comanda,
        'productos': productos,
        'detalles': detalles_actuales,
        'subtotal': subtotal,
        'token': token,
        'vencimiento': comanda.fecha_vencimiento_link,
    }

    return render(request, 'ventas/comanda_cliente/menu.html', context)


@require_http_methods(["POST"])
@csrf_exempt
def comanda_cliente_agregar_producto(request, token):
    """
    Agregar un producto a la comanda del cliente (AJAX)
    """
    try:
        # Validar comanda
        comanda = get_object_or_404(Comanda, token_acceso=token)

        if not comanda.es_link_valido():
            return JsonResponse({
                'success': False,
                'error': 'Link expirado'
            }, status=403)

        if comanda.estado not in ['borrador', 'pendiente_pago']:
            return JsonResponse({
                'success': False,
                'error': 'Comanda no editable'
            }, status=403)

        # Obtener datos del request
        data = json.loads(request.body)
        producto_id = data.get('producto_id')
        cantidad = int(data.get('cantidad', 1))

        if cantidad < 1:
            return JsonResponse({
                'success': False,
                'error': 'Cantidad inválida'
            }, status=400)

        # Validar producto
        producto = get_object_or_404(
            Producto,
            id=producto_id,
            comanda_cliente=True,
            activo=True
        )

        # Validar stock
        if producto.stock < cantidad:
            return JsonResponse({
                'success': False,
                'error': f'Stock insuficiente. Disponible: {producto.stock}'
            }, status=400)

        with transaction.atomic():
            # Buscar si ya existe un detalle para este producto
            detalle, created = DetalleComanda.objects.get_or_create(
                comanda=comanda,
                producto=producto,
                defaults={
                    'cantidad': cantidad,
                    'precio_unitario': producto.precio,
                    'notas': ''
                }
            )

            if not created:
                # Si ya existe, incrementar la cantidad
                detalle.cantidad += cantidad
                detalle.save()

            # Actualizar estado de la comanda si está en borrador
            if comanda.estado == 'borrador':
                comanda.estado = 'borrador'
                comanda.save()

            # Calcular nuevo total
            subtotal = sum(d.subtotal for d in comanda.detalles.all())

        return JsonResponse({
            'success': True,
            'mensaje': f'{producto.nombre} agregado al pedido',
            'detalle_id': detalle.id,
            'cantidad_total': detalle.cantidad,
            'subtotal_item': float(detalle.subtotal),
            'subtotal_comanda': float(subtotal)
        })

    except Exception as e:
        logger.error(f"Error al agregar producto a comanda: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al procesar la solicitud'
        }, status=500)


@require_http_methods(["POST"])
@csrf_exempt
def comanda_cliente_actualizar_cantidad(request, token):
    """
    Actualizar la cantidad de un producto en la comanda (AJAX)
    """
    try:
        comanda = get_object_or_404(Comanda, token_acceso=token)

        if not comanda.es_link_valido():
            return JsonResponse({
                'success': False,
                'error': 'Link expirado'
            }, status=403)

        data = json.loads(request.body)
        detalle_id = data.get('detalle_id')
        cantidad = int(data.get('cantidad', 0))

        detalle = get_object_or_404(DetalleComanda, id=detalle_id, comanda=comanda)

        with transaction.atomic():
            if cantidad <= 0:
                # Eliminar el detalle
                detalle.delete()
                mensaje = 'Producto eliminado del pedido'
            else:
                # Validar stock
                if detalle.producto.stock < cantidad:
                    return JsonResponse({
                        'success': False,
                        'error': f'Stock insuficiente. Disponible: {detalle.producto.stock}'
                    }, status=400)

                # Actualizar cantidad
                detalle.cantidad = cantidad
                detalle.save()
                mensaje = 'Cantidad actualizada'

            # Calcular nuevo total
            subtotal = sum(d.subtotal for d in comanda.detalles.all())

        return JsonResponse({
            'success': True,
            'mensaje': mensaje,
            'subtotal_item': float(detalle.subtotal) if cantidad > 0 else 0,
            'subtotal_comanda': float(subtotal)
        })

    except Exception as e:
        logger.error(f"Error al actualizar cantidad: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': 'Error al procesar la solicitud'
        }, status=500)


@require_http_methods(["POST"])
def comanda_cliente_finalizar(request, token):
    """
    Finalizar la comanda y proceder al pago con Flow
    """
    try:
        comanda = get_object_or_404(Comanda, token_acceso=token)

        if not comanda.es_link_valido():
            return JsonResponse({
                'success': False,
                'error': 'Link expirado'
            }, status=403)

        # Validar que tenga productos
        if not comanda.detalles.exists():
            return JsonResponse({
                'success': False,
                'error': 'Debe agregar al menos un producto al pedido'
            }, status=400)

        # Calcular total
        total = sum(d.subtotal for d in comanda.detalles.all())

        with transaction.atomic():
            # Actualizar estado a pendiente de pago
            comanda.estado = 'pendiente_pago'
            comanda.save()

            # Crear orden de pago en Flow
            flow_service = FlowService()

            # Preparar datos para Flow
            order_data = {
                'commerceOrder': f'COMANDA-{comanda.id}',
                'subject': f'Pedido Aremko Spa - Comanda #{comanda.id}',
                'currency': 'CLP',
                'amount': int(total),
                'email': comanda.venta_reserva.cliente.email if comanda.venta_reserva else 'cliente@aremko.cl',
                'urlConfirmation': f'{settings.SITE_URL}/ventas/comanda-cliente/{token}/pago-confirmacion/',
                'urlReturn': f'{settings.SITE_URL}/ventas/comanda-cliente/{token}/pago-retorno/',
            }

            # Crear pago en Flow
            response = flow_service.create_payment(order_data)

            if response.get('url') and response.get('token'):
                # Guardar token de Flow
                comanda.flow_token = response['token']
                comanda.flow_order_id = f'COMANDA-{comanda.id}'
                comanda.save()

                return JsonResponse({
                    'success': True,
                    'payment_url': response['url'] + '?token=' + response['token']
                })
            else:
                raise Exception('Error al crear pago en Flow')

    except Exception as e:
        logger.error(f"Error al finalizar comanda: {str(e)}", exc_info=True)

        # Revertir estado si falló
        if comanda.estado == 'pendiente_pago':
            comanda.estado = 'borrador'
            comanda.save()

        return JsonResponse({
            'success': False,
            'error': 'Error al procesar el pago. Por favor intente nuevamente.'
        }, status=500)


@csrf_exempt
def comanda_cliente_pago_confirmacion(request, token):
    """
    Webhook de confirmación de pago desde Flow
    """
    try:
        flow_token = request.POST.get('token')

        # Validar comanda
        comanda = get_object_or_404(Comanda, token_acceso=token, flow_token=flow_token)

        # Verificar pago con Flow
        flow_service = FlowService()
        payment_status = flow_service.get_payment_status(flow_token)

        if payment_status.get('status') == 2:  # Pago exitoso
            with transaction.atomic():
                comanda.estado = 'pago_confirmado'
                comanda.save()

                # Descontar stock de productos
                for detalle in comanda.detalles.all():
                    producto = detalle.producto
                    producto.stock -= detalle.cantidad
                    producto.save()

                logger.info(f'Pago confirmado para comanda {comanda.id}')
        else:
            comanda.estado = 'pago_fallido'
            comanda.save()
            logger.warning(f'Pago fallido para comanda {comanda.id}')

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.error(f"Error en confirmación de pago: {str(e)}", exc_info=True)
        return JsonResponse({'status': 'error'}, status=500)


def comanda_cliente_pago_retorno(request, token):
    """
    Página de retorno después del pago
    """
    comanda = get_object_or_404(Comanda, token_acceso=token)

    context = {
        'comanda': comanda,
        'exitoso': comanda.estado == 'pago_confirmado',
        'total': sum(d.subtotal for d in comanda.detalles.all())
    }

    return render(request, 'ventas/comanda_cliente/pago_resultado.html', context)
