# -*- coding: utf-8 -*-
"""
Vistas para integración con Mercado Pago Link
"""

import json
import logging
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
from ..models import VentaReserva
from ..services.mercadopago_service import mercadopago_service

logger = logging.getLogger(__name__)


@require_http_methods(["POST"])
def create_mercadopago_payment(request):
    """
    Crea un link de pago con Mercado Pago Link
    """
    try:
        data = json.loads(request.body)
        reserva_id = data.get('reserva_id')
        
        if not reserva_id:
            return JsonResponse({'error': 'reserva_id es requerido'}, status=400)
        
        # Obtener la reserva
        try:
            reserva = VentaReserva.objects.get(id=reserva_id)
        except VentaReserva.DoesNotExist:
            return JsonResponse({'error': 'Reserva no encontrada'}, status=404)
        
        # Verificar que la reserva no esté ya pagada
        if reserva.estado_pago == 'pagado':
            return JsonResponse({'error': 'La reserva ya está pagada'}, status=400)
        
        # Crear link de pago
        result = mercadopago_service.create_payment_link(
            reserva_id=reserva_id,
            amount=float(reserva.total),
            description=f"Reserva Aremko #{reserva_id}",
            customer_email=reserva.cliente.email,
            customer_name=reserva.cliente.nombre
        )
        
        if result.get('success'):
            return JsonResponse({
                'success': True,
                'payment_link': result.get('payment_link'),
                'preference_id': result.get('preference_id'),
                'sandbox_link': result.get('sandbox_init_point')
            })
        else:
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Error desconocido')
            }, status=500)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'JSON inválido'}, status=400)
    except Exception as e:
        logger.error(f"Error en create_mercadopago_payment: {str(e)}")
        return JsonResponse({'error': 'Error interno del servidor'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def mercadopago_webhook(request):
    """
    Webhook para recibir notificaciones de Mercado Pago
    """
    try:
        # Obtener datos del webhook
        data = json.loads(request.body)
        
        # Procesar webhook
        result = mercadopago_service.process_webhook(data)
        
        if result.get('success'):
            return HttpResponse('OK', status=200)
        else:
            logger.error(f"Error procesando webhook: {result.get('error')}")
            return HttpResponse('Error', status=400)
            
    except json.JSONDecodeError:
        return HttpResponse('JSON inválido', status=400)
    except Exception as e:
        logger.error(f"Error en webhook Mercado Pago: {str(e)}")
        return HttpResponse('Error interno', status=500)


def mercadopago_success(request):
    """
    Página de éxito después del pago
    """
    reserva_id = request.GET.get('reserva_id')
    payment_id = request.GET.get('payment_id')
    
    if reserva_id:
        try:
            reserva = VentaReserva.objects.get(id=reserva_id)
            context = {
                'reserva': reserva,
                'payment_id': payment_id,
                'success': True
            }
            return render(request, 'ventas/payment_success.html', context)
        except VentaReserva.DoesNotExist:
            messages.error(request, 'Reserva no encontrada')
    
    return redirect('ventas:checkout')


def mercadopago_failure(request):
    """
    Página de fallo en el pago
    """
    reserva_id = request.GET.get('reserva_id')
    
    if reserva_id:
        try:
            reserva = VentaReserva.objects.get(id=reserva_id)
            context = {
                'reserva': reserva,
                'success': False
            }
            return render(request, 'ventas/payment_failure.html', context)
        except VentaReserva.DoesNotExist:
            messages.error(request, 'Reserva no encontrada')
    
    return redirect('ventas:checkout')


def mercadopago_pending(request):
    """
    Página de pago pendiente
    """
    reserva_id = request.GET.get('reserva_id')
    
    if reserva_id:
        try:
            reserva = VentaReserva.objects.get(id=reserva_id)
            context = {
                'reserva': reserva,
                'pending': True
            }
            return render(request, 'ventas/payment_pending.html', context)
        except VentaReserva.DoesNotExist:
            messages.error(request, 'Reserva no encontrada')
    
    return redirect('ventas:checkout')


def mercadopago_payment_status(request, reserva_id):
    """
    API para verificar el estado del pago de una reserva
    """
    try:
        reserva = get_object_or_404(VentaReserva, id=reserva_id)
        
        # Verificar si hay pagos de Mercado Pago Link
        pagos_mp = reserva.pagos.filter(metodo_pago='mercadopago_link')
        
        if pagos_mp.exists():
            ultimo_pago = pagos_mp.latest('fecha_pago')
            return JsonResponse({
                'success': True,
                'paid': True,
                'payment_date': ultimo_pago.fecha_pago.isoformat(),
                'amount': float(ultimo_pago.monto),
                'method': ultimo_pago.metodo_pago
            })
        else:
            return JsonResponse({
                'success': True,
                'paid': False,
                'message': 'No hay pagos de Mercado Pago Link registrados'
            })
            
    except Exception as e:
        logger.error(f"Error verificando estado pago: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)