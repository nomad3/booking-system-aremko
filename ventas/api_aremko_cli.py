"""
API REST para aremko-cli
Endpoints de solo lectura para consultar estadísticas de reservas
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Avg, Count, Q
from django.utils import timezone
from datetime import datetime, timedelta
from .models import VentaReserva, Cliente, ReservaServicio
import logging

logger = logging.getLogger(__name__)


def parse_date(date_str):
    """Parse date string in format YYYY-MM-DD"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date()
    except (ValueError, AttributeError):
        return None


@csrf_exempt
@require_http_methods(["GET"])
def bookings_stats(request):
    """
    Estadísticas de reservas para aremko-cli

    Query params:
        date_start: Fecha inicio (YYYY-MM-DD)
        date_stop: Fecha fin (YYYY-MM-DD)

    Returns:
        {
            "success": true,
            "data": {
                "total": 48,
                "revenue": 2840000,
                "avg_ticket": 59167,
                "period": {
                    "start": "2026-05-02",
                    "end": "2026-05-09"
                }
            }
        }
    """
    try:
        # Obtener parámetros de fecha
        date_start_str = request.GET.get('date_start')
        date_stop_str = request.GET.get('date_stop')

        # Si no hay fechas, usar última semana
        if not date_start_str or not date_stop_str:
            date_stop = timezone.now().date()
            date_start = date_stop - timedelta(days=7)
        else:
            date_start = parse_date(date_start_str)
            date_stop = parse_date(date_stop_str)

            if not date_start or not date_stop:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'
                }, status=400)

        # Consultar reservas en el período
        reservas = VentaReserva.objects.filter(
            fecha_creacion__date__gte=date_start,
            fecha_creacion__date__lte=date_stop
        ).exclude(
            estado_pago='cancelado'  # Excluir canceladas
        )

        # Calcular estadísticas
        stats = reservas.aggregate(
            total_count=Count('id'),
            total_revenue=Sum('total'),
            avg_ticket=Avg('total')
        )

        # Preparar respuesta
        response_data = {
            'success': True,
            'data': {
                'total': stats['total_count'] or 0,
                'revenue': float(stats['total_revenue'] or 0),
                'avg_ticket': float(stats['avg_ticket'] or 0),
                'period': {
                    'start': date_start.strftime('%Y-%m-%d'),
                    'end': date_stop.strftime('%Y-%m-%d')
                },
                # Estadísticas adicionales
                'paid': reservas.filter(estado_pago='pagado').count(),
                'pending': reservas.filter(estado_pago='pendiente').count(),
                'partial': reservas.filter(estado_pago='parcial').count(),
            }
        }

        logger.info(f"aremko-cli: Bookings stats requested for {date_start} to {date_stop}")
        return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Error in bookings_stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def bookings_daily(request):
    """
    Reservas agrupadas por día

    Query params:
        date_start: Fecha inicio (YYYY-MM-DD)
        date_stop: Fecha fin (YYYY-MM-DD)

    Returns:
        {
            "success": true,
            "data": [
                {
                    "date": "2026-05-02",
                    "count": 5,
                    "revenue": 295000
                },
                ...
            ]
        }
    """
    try:
        date_start_str = request.GET.get('date_start')
        date_stop_str = request.GET.get('date_stop')

        if not date_start_str or not date_stop_str:
            date_stop = timezone.now().date()
            date_start = date_stop - timedelta(days=7)
        else:
            date_start = parse_date(date_start_str)
            date_stop = parse_date(date_stop_str)

        # Consultar reservas agrupadas por día
        reservas_por_dia = VentaReserva.objects.filter(
            fecha_creacion__date__gte=date_start,
            fecha_creacion__date__lte=date_stop
        ).exclude(
            estado_pago='cancelado'
        ).extra(
            select={'day': 'date(fecha_creacion)'}
        ).values('day').annotate(
            count=Count('id'),
            revenue=Sum('total')
        ).order_by('day')

        # Formatear respuesta
        daily_data = [
            {
                'date': item['day'].strftime('%Y-%m-%d'),
                'count': item['count'],
                'revenue': float(item['revenue'] or 0)
            }
            for item in reservas_por_dia
        ]

        return JsonResponse({
            'success': True,
            'data': daily_data
        })

    except Exception as e:
        logger.error(f"Error in bookings_daily: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def clients_stats(request):
    """
    Estadísticas de clientes

    Returns:
        {
            "success": true,
            "data": {
                "total_clients": 1250,
                "new_clients_week": 15,
                "returning_clients_week": 10
            }
        }
    """
    try:
        date_stop = timezone.now().date()
        date_start = date_stop - timedelta(days=7)

        # Total de clientes
        total_clients = Cliente.objects.count()

        # Clientes nuevos esta semana
        new_clients = Cliente.objects.filter(
            created_at__date__gte=date_start,
            created_at__date__lte=date_stop
        ).count()

        # Clientes que regresaron esta semana
        returning_clients = VentaReserva.objects.filter(
            fecha_creacion__date__gte=date_start,
            fecha_creacion__date__lte=date_stop
        ).values('cliente').annotate(
            bookings_count=Count('id')
        ).filter(bookings_count__gt=1).count()

        return JsonResponse({
            'success': True,
            'data': {
                'total_clients': total_clients,
                'new_clients_week': new_clients,
                'returning_clients_week': returning_clients,
                'period': {
                    'start': date_start.strftime('%Y-%m-%d'),
                    'end': date_stop.strftime('%Y-%m-%d')
                }
            }
        })

    except Exception as e:
        logger.error(f"Error in clients_stats: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def health_check(request):
    """
    Health check para verificar que la API está funcionando
    """
    return JsonResponse({
        'success': True,
        'status': 'healthy',
        'service': 'aremko-cli-api',
        'version': '1.0.0',
        'timestamp': timezone.now().isoformat()
    })
