"""
API REST para aremko-cli
Endpoints de solo lectura para consultar estadísticas de reservas
"""

from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum, Avg, Count, Q, Min, F
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import datetime, timedelta, date as _date_cls
from .models import VentaReserva, Cliente, ReservaServicio, Pago
import logging

# Mapeo unico de tipos de servicio a nombres de familia.
# Reusado por bookings_by_family y bookings_weekly_breakdown.
FAMILY_NAMES = {
    'masaje': 'Masajes',
    'tina': 'Tinas',
    'cabana': 'Cabañas',
    'otro': 'Otros',
}

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
    Estadísticas de clientes en el periodo dado.

    Query params:
        date_start (YYYY-MM-DD, opcional): inicio del periodo. Default = hoy - 7 dias.
        date_stop  (YYYY-MM-DD, opcional): fin del periodo. Default = hoy.

    Definiciones:
        - unique_clients_week: clientes con al menos una VentaReserva no cancelada
          cuya fecha_creacion cae dentro de [date_start, date_stop].
        - new_clients_week: clientes cuya PRIMERA VentaReserva (historica, no
          cancelada) cae dentro del periodo.
        - returning_clients_week: clientes con venta en el periodo Y otra venta
          (no cancelada) ANTES de date_start. Equivale a unique - new.

    Returns:
        {
          "success": true,
          "data": {
            "total_clients": 1250,
            "new_clients_week": 15,
            "returning_clients_week": 10,
            "unique_clients_week": 25,
            "period": {"start": "...", "end": "..."}
          }
        }
    """
    try:
        # Periodo: query params con fallback a ultimos 7 dias.
        date_start_str = request.GET.get('date_start')
        date_stop_str = request.GET.get('date_stop')
        if date_start_str and date_stop_str:
            date_start = parse_date(date_start_str)
            date_stop = parse_date(date_stop_str)
            if not date_start or not date_stop:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'
                }, status=400)
        else:
            date_stop = timezone.now().date()
            date_start = date_stop - timedelta(days=7)

        total_clients = Cliente.objects.count()

        # Clientes unicos con venta en el periodo (excluyendo canceladas).
        clientes_en_periodo_qs = VentaReserva.objects.filter(
            fecha_creacion__date__gte=date_start,
            fecha_creacion__date__lte=date_stop,
        ).exclude(estado_pago='cancelado').values_list('cliente_id', flat=True).distinct()
        clientes_en_periodo = set(clientes_en_periodo_qs)
        unique_clients = len(clientes_en_periodo)

        # Recurrentes: clientes del periodo que YA tenian una venta antes de date_start.
        returning_clients = VentaReserva.objects.filter(
            cliente_id__in=clientes_en_periodo,
            fecha_creacion__date__lt=date_start,
        ).exclude(estado_pago='cancelado').values('cliente_id').distinct().count()

        # Nuevos: los del periodo que no son recurrentes (su primera venta cae aqui).
        new_clients = unique_clients - returning_clients

        return JsonResponse({
            'success': True,
            'data': {
                'total_clients': total_clients,
                'new_clients_week': new_clients,
                'returning_clients_week': returning_clients,
                'unique_clients_week': unique_clients,
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
def bookings_by_family(request):
    """
    Estadísticas de reservas agrupadas por familia de servicio con comparativas

    Query params:
        date_start: Fecha inicio (YYYY-MM-DD)
        date_stop: Fecha fin (YYYY-MM-DD)

    Returns:
        {
            "success": true,
            "data": [
                {
                    "family": "Masajes",
                    "current_count": 32,
                    "previous_month_count": 28,
                    "previous_year_count": 25
                },
                ...
            ]
        }
    """
    try:
        # Obtener parámetros de fecha
        date_start_str = request.GET.get('date_start')
        date_stop_str = request.GET.get('date_stop')

        # Si no hay fechas, usar desde día 1 hasta hoy del mes actual
        if not date_start_str or not date_stop_str:
            today = timezone.now().date()
            date_start = today.replace(day=1)
            date_stop = today
        else:
            date_start = parse_date(date_start_str)
            date_stop = parse_date(date_stop_str)

            if not date_start or not date_stop:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'
                }, status=400)

        # Calcular día del mes para comparativas (usar mismo día)
        day_of_month = date_stop.day

        # Mes anterior: mismo día del mes anterior
        if date_start.month == 1:
            prev_month_start = date_start.replace(year=date_start.year - 1, month=12)
            try:
                prev_month_stop = prev_month_start.replace(day=day_of_month)
            except ValueError:
                # Si el día no existe en el mes anterior (ej: 31 en feb), usar último día
                import calendar
                last_day = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
                prev_month_stop = prev_month_start.replace(day=last_day)
        else:
            prev_month_start = date_start.replace(month=date_start.month - 1)
            try:
                prev_month_stop = prev_month_start.replace(day=day_of_month)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
                prev_month_stop = prev_month_start.replace(day=last_day)

        # Año anterior: mismo mes y día pero del año anterior
        prev_year_start = date_start.replace(year=date_start.year - 1)
        try:
            prev_year_stop = date_stop.replace(year=date_stop.year - 1)
        except ValueError:
            # Caso 29 feb en año no bisiesto
            prev_year_stop = prev_year_start.replace(day=28)

        # Mapeo unificado (ver FAMILY_NAMES al inicio del modulo).
        family_names = FAMILY_NAMES

        def get_family_stats(start_date, end_date):
            """Helper para obtener stats de un período.

            Revenue calculado como precio_unitario × cantidad_personas (con fallback
            a servicio.precio_base si precio_unitario es null). Mismo criterio que el
            dashboard interno (analytics_views.py).
            """
            stats = ReservaServicio.objects.filter(
                venta_reserva__fecha_creacion__date__gte=start_date,
                venta_reserva__fecha_creacion__date__lte=end_date
            ).exclude(
                venta_reserva__estado_pago='cancelado'
            ).values(
                'servicio__tipo_servicio'
            ).annotate(
                count=Count('id'),
                revenue=Sum(
                    Coalesce(F('precio_unitario_venta'), F('servicio__precio_base'))
                    * F('cantidad_personas')
                ),
            )

            # Convertir a dict para fácil acceso
            result = {}
            for stat in stats:
                tipo = stat['servicio__tipo_servicio']
                result[tipo] = {
                    'count': stat['count'],
                    'revenue': float(stat['revenue'] or 0)
                }
            return result

        # Obtener stats para cada período
        current_stats = get_family_stats(date_start, date_stop)
        prev_month_stats = get_family_stats(prev_month_start, prev_month_stop)
        prev_year_stats = get_family_stats(prev_year_start, prev_year_stop)

        # Combinar todas las familias (todas las que aparecen en cualquier período)
        all_families = set(current_stats.keys()) | set(prev_month_stats.keys()) | set(prev_year_stats.keys())

        # Formatear respuesta
        family_stats = []
        for tipo in all_families:
            family_name = family_names.get(tipo, tipo.capitalize())
            current = current_stats.get(tipo, {'count': 0, 'revenue': 0})
            prev_month = prev_month_stats.get(tipo, {'count': 0, 'revenue': 0})
            prev_year = prev_year_stats.get(tipo, {'count': 0, 'revenue': 0})

            family_stats.append({
                'family': family_name,
                'current_count': current['count'],
                'current_revenue': current['revenue'],
                'previous_month_count': prev_month['count'],
                'previous_month_revenue': prev_month['revenue'],
                'previous_year_count': prev_year['count'],
                'previous_year_revenue': prev_year['revenue']
            })

        # Ordenar por current_revenue descendente
        family_stats.sort(key=lambda x: x['current_revenue'], reverse=True)

        logger.info(f"aremko-cli: Family stats requested for {date_start} to {date_stop}")
        return JsonResponse({
            'success': True,
            'data': family_stats
        })

    except Exception as e:
        logger.error(f"Error in bookings_by_family: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def _get_family_stats_range(start_date, end_date):
    """Helper compartido: stats por familia entre dos fechas.

    Excluye ventas canceladas. Revenue = precio_unitario × cantidad_personas
    con fallback a servicio.precio_base.
    """
    stats = ReservaServicio.objects.filter(
        venta_reserva__fecha_creacion__date__gte=start_date,
        venta_reserva__fecha_creacion__date__lte=end_date,
    ).exclude(
        venta_reserva__estado_pago='cancelado',
    ).values('servicio__tipo_servicio').annotate(
        count=Count('id'),
        revenue=Sum(
            Coalesce(F('precio_unitario_venta'), F('servicio__precio_base'))
            * F('cantidad_personas')
        ),
    )
    result = {}
    for stat in stats:
        tipo = stat['servicio__tipo_servicio']
        result[tipo] = {
            'count': stat['count'],
            'revenue': float(stat['revenue'] or 0),
        }
    return result


@csrf_exempt
@require_http_methods(["GET"])
def bookings_by_family_mtd(request):
    """
    Ventas por familia — Month To Date (1ro del mes a hoy/ayer) + comparativas
    mismo rango mes anterior y año anterior.

    Query params:
        date_stop (YYYY-MM-DD, opcional): fin del rango actual.
            Default = ayer (timezone Chile).

    Lógica de rangos (ejemplo si date_stop = 2026-05-18):
        - Actual:        2026-05-01 → 2026-05-18
        - Mes anterior:  2026-04-01 → 2026-04-18 (mismo día del mes anterior)
        - Año anterior:  2025-05-01 → 2025-05-18

    Si el día del mes no existe en el mes anterior (ej: 31 → feb), se ajusta
    al último día del mes. Mismo criterio para año bisiesto.

    Response:
        {
          "success": true,
          "data": {
            "period": {"current_start": "...", "current_stop": "...", ...},
            "families": [{"family": "...", "current_count": N, "current_revenue": X,
                          "previous_month_count": ..., "previous_month_revenue": ...,
                          "previous_year_count": ..., "previous_year_revenue": ...}, ...]
          }
        }
    """
    import calendar

    try:
        date_stop_str = request.GET.get('date_stop')
        if date_stop_str:
            date_stop = parse_date(date_stop_str)
            if not date_stop:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de fecha inválido. Usa YYYY-MM-DD',
                }, status=400)
        else:
            date_stop = timezone.now().date() - timedelta(days=1)

        # Inicio del mes actual.
        current_start = date_stop.replace(day=1)
        day_of_month = date_stop.day

        # Mes anterior: mismo dia del mes anterior.
        if current_start.month == 1:
            prev_month_start = current_start.replace(year=current_start.year - 1, month=12)
        else:
            prev_month_start = current_start.replace(month=current_start.month - 1)

        last_day_prev_month = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
        prev_month_stop = prev_month_start.replace(
            day=min(day_of_month, last_day_prev_month)
        )

        # Año anterior: mismo mes + dia, año - 1.
        prev_year_start = current_start.replace(year=current_start.year - 1)
        try:
            prev_year_stop = date_stop.replace(year=date_stop.year - 1)
        except ValueError:
            # 29-feb en año no bisiesto → 28-feb.
            prev_year_stop = prev_year_start.replace(
                day=calendar.monthrange(prev_year_start.year, prev_year_start.month)[1]
            )

        # Stats por familia para cada periodo.
        current_stats = _get_family_stats_range(current_start, date_stop)
        prev_month_stats = _get_family_stats_range(prev_month_start, prev_month_stop)
        prev_year_stats = _get_family_stats_range(prev_year_start, prev_year_stop)

        all_families = (
            set(current_stats.keys())
            | set(prev_month_stats.keys())
            | set(prev_year_stats.keys())
        )

        families_data = []
        for tipo in all_families:
            family_name = FAMILY_NAMES.get(tipo, (tipo or 'otro').capitalize())
            cur = current_stats.get(tipo, {'count': 0, 'revenue': 0})
            pm = prev_month_stats.get(tipo, {'count': 0, 'revenue': 0})
            py = prev_year_stats.get(tipo, {'count': 0, 'revenue': 0})
            families_data.append({
                'family': family_name,
                'current_count': cur['count'],
                'current_revenue': cur['revenue'],
                'previous_month_count': pm['count'],
                'previous_month_revenue': pm['revenue'],
                'previous_year_count': py['count'],
                'previous_year_revenue': py['revenue'],
            })

        families_data.sort(key=lambda x: x['current_revenue'], reverse=True)

        logger.info(
            f"aremko-cli: by_family_mtd current={current_start}→{date_stop} "
            f"prev_month={prev_month_start}→{prev_month_stop} "
            f"prev_year={prev_year_start}→{prev_year_stop}"
        )
        return JsonResponse({
            'success': True,
            'data': {
                'period': {
                    'current_start': current_start.strftime('%Y-%m-%d'),
                    'current_stop': date_stop.strftime('%Y-%m-%d'),
                    'prev_month_start': prev_month_start.strftime('%Y-%m-%d'),
                    'prev_month_stop': prev_month_stop.strftime('%Y-%m-%d'),
                    'prev_year_start': prev_year_start.strftime('%Y-%m-%d'),
                    'prev_year_stop': prev_year_stop.strftime('%Y-%m-%d'),
                },
                'families': families_data,
            },
        })

    except Exception as e:
        logger.error(f"Error in bookings_by_family_mtd: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e),
        }, status=500)


# Mapeo inverso: familia (frontend / NL) → tipo_servicio en BD.
FAMILIA_TO_TIPO = {
    'tinas': 'tina',
    'masajes': 'masaje',
    'cabanas': 'cabana',
    'cabañas': 'cabana',
    'alojamiento': 'cabana',
    'otros': 'otro',
}

DETALLE_HARD_LIMIT = 500
DETALLE_MAX_DAYS = 92


@csrf_exempt
@require_http_methods(["GET"])
def bookings_detalle(request):
    """
    Detalle fila-por-fila de servicios reservados en un rango de fechas.
    Pensado para consumirse desde una consulta NL en aremko-cli.

    Query params:
        fecha_desde (YYYY-MM-DD, requerido si no hay cliente)
        fecha_hasta (YYYY-MM-DD, requerido si no hay cliente)
        familia      (opcional: tinas/masajes/cabanas/otros)
        servicio     (opcional: match parcial icontains contra nombre del servicio)
        proveedor    (opcional: match icontains contra proveedor_asignado.nombre — masajista)
        cliente      (opcional: match icontains contra nombre/telefono/email/documento_identidad).
                     Cuando se usa: las fechas son opcionales (default desde 2000) y NO aplica
                     el cap de 92 días — se trae historial completo del cliente.
        limit        (opcional, default 500, máx 500 hardcoded)

    Filtra por `ReservaServicio.fecha_agendamiento` (fecha del servicio, no de la venta).
    Excluye estado_pago='cancelado'.
    Orden: fecha_agendamiento DESC, hora_inicio DESC.
    """
    from django.db import connection, transaction
    from django.db.models import Q
    from datetime import date

    # Filtros base
    cliente_filtro = (request.GET.get('cliente') or '').strip()
    fecha_desde_str = request.GET.get('fecha_desde')
    fecha_hasta_str = request.GET.get('fecha_hasta')

    # Si hay filtro de cliente, las fechas son opcionales (historial completo).
    # Si NO hay cliente, las fechas son obligatorias y el rango se limita a 92 días.
    if cliente_filtro:
        if fecha_desde_str:
            fecha_desde = parse_date(fecha_desde_str)
            if not fecha_desde:
                return JsonResponse({'error': 'Formato de fecha_desde inválido. Usa YYYY-MM-DD'}, status=400)
        else:
            fecha_desde = date(2000, 1, 1)

        if fecha_hasta_str:
            fecha_hasta = parse_date(fecha_hasta_str)
            if not fecha_hasta:
                return JsonResponse({'error': 'Formato de fecha_hasta inválido. Usa YYYY-MM-DD'}, status=400)
        else:
            fecha_hasta = timezone.now().date()

        if fecha_desde > fecha_hasta:
            return JsonResponse({'error': 'fecha_desde no puede ser mayor que fecha_hasta'}, status=400)
        # Sin cap de 92 días: el filtro de cliente acota el resultado naturalmente.
    else:
        if not fecha_desde_str or not fecha_hasta_str:
            return JsonResponse({
                'error': 'fecha_desde y fecha_hasta son requeridos (YYYY-MM-DD) cuando no se filtra por cliente',
            }, status=400)

        fecha_desde = parse_date(fecha_desde_str)
        fecha_hasta = parse_date(fecha_hasta_str)
        if not fecha_desde or not fecha_hasta:
            return JsonResponse({'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'}, status=400)

        if fecha_desde > fecha_hasta:
            return JsonResponse({'error': 'fecha_desde no puede ser mayor que fecha_hasta'}, status=400)

        if (fecha_hasta - fecha_desde).days > DETALLE_MAX_DAYS:
            return JsonResponse({
                'error': f'rango máximo {DETALLE_MAX_DAYS} días (~3 meses) cuando no se filtra por cliente',
            }, status=400)

    # Familia (opcional)
    familia_str = (request.GET.get('familia') or '').strip().lower()
    tipo_servicio_filtro = None
    if familia_str:
        if familia_str not in FAMILIA_TO_TIPO:
            return JsonResponse({
                'error': f'familia inválida. Opciones: {", ".join(sorted(set(FAMILIA_TO_TIPO.keys())))}',
            }, status=400)
        tipo_servicio_filtro = FAMILIA_TO_TIPO[familia_str]

    # Servicio (opcional, match parcial)
    servicio_filtro = (request.GET.get('servicio') or '').strip()

    # Proveedor/masajista (opcional, match parcial)
    proveedor_filtro = (request.GET.get('proveedor') or '').strip()

    # Límite (hard cap 500)
    try:
        limit = int(request.GET.get('limit', DETALLE_HARD_LIMIT))
    except (TypeError, ValueError):
        limit = DETALLE_HARD_LIMIT
    limit = max(1, min(DETALLE_HARD_LIMIT, limit))

    # Mapeo tipo_servicio → nombre de familia para el response.
    tipo_a_familia = {tipo: name for tipo, name in FAMILY_NAMES.items()}

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # statement_timeout local: protege la BD si la query degrada.
                try:
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                except Exception:
                    pass  # SQLite en tests no soporta esto.

            qs = ReservaServicio.objects.select_related(
                'servicio', 'venta_reserva', 'venta_reserva__cliente', 'proveedor_asignado',
            ).filter(
                fecha_agendamiento__gte=fecha_desde,
                fecha_agendamiento__lte=fecha_hasta,
            ).exclude(
                venta_reserva__estado_pago='cancelado',
            )

            if tipo_servicio_filtro:
                qs = qs.filter(servicio__tipo_servicio=tipo_servicio_filtro)

            if servicio_filtro:
                qs = qs.filter(servicio__nombre__icontains=servicio_filtro)

            if proveedor_filtro:
                qs = qs.filter(proveedor_asignado__nombre__icontains=proveedor_filtro)

            if cliente_filtro:
                # Match parcial sobre 4 campos del cliente. icontains soporta
                # substrings (ej: '958655810' matchea teléfono '+56958655810').
                qs = qs.filter(
                    Q(venta_reserva__cliente__nombre__icontains=cliente_filtro) |
                    Q(venta_reserva__cliente__telefono__icontains=cliente_filtro) |
                    Q(venta_reserva__cliente__email__icontains=cliente_filtro) |
                    Q(venta_reserva__cliente__documento_identidad__icontains=cliente_filtro)
                )

            qs = qs.order_by('-fecha_agendamiento', '-hora_inicio', '-id').distinct()

            # Pedimos limit + 1 para detectar truncated.
            rows_qs = list(qs[:limit + 1])
            truncated = len(rows_qs) > limit
            rows_qs = rows_qs[:limit]

            # Deduplicación defensiva por ReservaServicio.id (por si select_related
            # genera filas repetidas por algún JOIN inesperado).
            seen_ids = set()
            unique_rows = []
            for r in rows_qs:
                if r.id in seen_ids:
                    continue
                seen_ids.add(r.id)
                unique_rows.append(r)
            rows_qs = unique_rows

            # Pre-cargar metodos de pago de las ventas involucradas (1 query).
            venta_ids = {r.venta_reserva_id for r in rows_qs}
            metodos_por_venta = {}
            if venta_ids:
                pagos_qs = Pago.objects.filter(
                    venta_reserva_id__in=venta_ids,
                ).order_by('venta_reserva_id', '-fecha_pago').values(
                    'venta_reserva_id', 'metodo_pago',
                )
                for p in pagos_qs:
                    metodos_por_venta.setdefault(p['venta_reserva_id'], p['metodo_pago'])

            # Agrupar líneas equivalentes de la misma reserva. Caso típico:
            # una pareja reserva 2 masajes del mismo servicio para el mismo
            # horario — el sistema crea 2 ReservaServicio (una por persona/
            # proveedor). Para el reporte queremos verlo como UNA línea con
            # cantidad_personas=2, no como 2 líneas duplicadas.
            grupos = {}  # key: (venta_id, servicio_id, fecha, hora, precio) → dict
            orden_grupos = []
            for r in rows_qs:
                servicio = r.servicio
                venta = r.venta_reserva
                if not venta or not servicio:
                    continue

                precio_unit = r.precio_unitario_venta
                if precio_unit is None:
                    precio_unit = servicio.precio_base
                precio_unit = int(precio_unit or 0)

                # Incluimos proveedor_asignado_id en la clave: dos masajes con
                # mismo servicio/hora pero distintos masajistas son atenciones
                # legítimamente separadas (no se deben agrupar).
                key = (
                    venta.id,
                    servicio.id,
                    r.fecha_agendamiento,
                    r.hora_inicio,
                    precio_unit,
                    r.proveedor_asignado_id,
                )

                if key in grupos:
                    grupo = grupos[key]
                    grupo['cantidad_personas'] += (r.cantidad_personas or 1)
                    grupo['_linea_ids'].append(r.id)
                else:
                    grupos[key] = {
                        '_linea_ids': [r.id],
                        'venta': venta,
                        'servicio': servicio,
                        'cliente': venta.cliente if venta else None,
                        'proveedor': r.proveedor_asignado,
                        'fecha_agendamiento': r.fecha_agendamiento,
                        'hora_inicio': r.hora_inicio,
                        'cantidad_personas': r.cantidad_personas or 1,
                        'precio_unitario': precio_unit,
                    }
                    orden_grupos.append(key)

            rows = []
            total_revenue = 0
            for key in orden_grupos:
                g = grupos[key]
                servicio = g['servicio']
                venta = g['venta']
                cliente = g['cliente']
                proveedor = g['proveedor']
                cantidad = g['cantidad_personas']
                precio_unit = g['precio_unitario']
                total = precio_unit * cantidad
                total_revenue += total

                tipo = getattr(servicio, 'tipo_servicio', None) or 'otro'
                familia_nombre = tipo_a_familia.get(tipo, 'Otros')

                rows.append({
                    'linea_ids': g['_linea_ids'],  # lista de ReservaServicio.id agrupados
                    'reserva_id': venta.id,
                    'fecha': g['fecha_agendamiento'].isoformat() if g['fecha_agendamiento'] else None,
                    'hora': g['hora_inicio'],
                    'cliente_id': cliente.id if cliente else None,
                    'cliente_nombre': cliente.nombre if cliente else None,
                    'cliente_rut': (cliente.documento_identidad or None) if cliente else None,
                    'cliente_email': (cliente.email or None) if cliente else None,
                    'servicio_id': servicio.id,
                    'servicio_nombre': servicio.nombre,
                    'familia': familia_nombre,
                    'cantidad_personas': cantidad,
                    'precio_unitario': precio_unit,
                    'total': total,
                    'proveedor_id': proveedor.id if proveedor else None,
                    'proveedor_nombre': proveedor.nombre if proveedor else None,
                    'metodo_pago': metodos_por_venta.get(venta.id),
                    'estado': venta.estado_pago,
                    'nota': venta.comentarios or None,
                })

        logger.info(
            f"aremko-cli: bookings_detalle {fecha_desde}→{fecha_hasta} "
            f"familia={familia_str or '-'} servicio={servicio_filtro or '-'} "
            f"filas={len(rows)} truncated={truncated}"
        )
        return JsonResponse({
            'fecha_desde': fecha_desde.isoformat(),
            'fecha_hasta': fecha_hasta.isoformat(),
            'familia': familia_str or None,
            'servicio': servicio_filtro or None,
            'total_filas': len(rows),
            'total_revenue': total_revenue,
            'truncated': truncated,
            'rows': rows,
        })

    except Exception as e:
        logger.error(f"Error in bookings_detalle: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def bookings_by_payment_method(request):
    """
    Estadísticas de pagos agrupadas por método de pago con comparativas

    Query params:
        date_start: Fecha inicio (YYYY-MM-DD)
        date_stop: Fecha fin (YYYY-MM-DD)

    Returns:
        {
            "success": true,
            "data": [
                {
                    "payment_method": "Transferencia",
                    "current_count": 32,
                    "current_revenue": 1280000.0,
                    "previous_month_count": 28,
                    "previous_month_revenue": 1100000.0,
                    "previous_year_count": 25,
                    "previous_year_revenue": 950000.0
                },
                ...
            ]
        }
    """
    try:
        # Obtener parámetros de fecha
        date_start_str = request.GET.get('date_start')
        date_stop_str = request.GET.get('date_stop')

        # Si no hay fechas, usar desde día 1 hasta hoy del mes actual
        if not date_start_str or not date_stop_str:
            today = timezone.now().date()
            date_start = today.replace(day=1)
            date_stop = today
        else:
            date_start = parse_date(date_start_str)
            date_stop = parse_date(date_stop_str)

            if not date_start or not date_stop:
                return JsonResponse({
                    'success': False,
                    'error': 'Formato de fecha inválido. Usa YYYY-MM-DD'
                }, status=400)

        # Calcular día del mes para comparativas (usar mismo día)
        day_of_month = date_stop.day

        # Mes anterior
        if date_start.month == 1:
            prev_month_start = date_start.replace(year=date_start.year - 1, month=12)
            try:
                prev_month_stop = prev_month_start.replace(day=day_of_month)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
                prev_month_stop = prev_month_start.replace(day=last_day)
        else:
            prev_month_start = date_start.replace(month=date_start.month - 1)
            try:
                prev_month_stop = prev_month_start.replace(day=day_of_month)
            except ValueError:
                import calendar
                last_day = calendar.monthrange(prev_month_start.year, prev_month_start.month)[1]
                prev_month_stop = prev_month_start.replace(day=last_day)

        # Año anterior
        prev_year_start = date_start.replace(year=date_start.year - 1)
        try:
            prev_year_stop = date_stop.replace(year=date_stop.year - 1)
        except ValueError:
            prev_year_stop = prev_year_start.replace(day=28)

        # Mapeo de métodos de pago a nombres simplificados
        payment_method_map = {
            'tarjeta': 'Tarjeta',
            'efectivo': 'Efectivo',
            'transferencia': 'Transferencia',
            'webpay': 'WebPay',
            'flow': 'Flow',
            'mercadopago': 'Mercado Pago',
            'mercadopago_link': 'Mercado Pago',
            'giftcard': 'Gift Card',
            'descuento': 'Descuento',
            'scotiabank': 'Transferencia',
            'bancoestado': 'Transferencia',
            'cuentarut': 'Transferencia',
            'machjorge': 'Mach',
            'machalda': 'Mach',
            'bicegoalda': 'Transferencia',
            'bcialda': 'Transferencia',
            'andesalda': 'Transferencia',
            'mercadopagoaremko': 'Mercado Pago',
            'scotiabankalda': 'Transferencia',
            'copecjorge': 'Copec',
            'copecalda': 'Copec',
            'booking': 'Booking',
        }

        def get_payment_stats(start_date, end_date):
            """Helper para obtener stats de pagos en un período"""
            stats = Pago.objects.filter(
                fecha_pago__date__gte=start_date,
                fecha_pago__date__lte=end_date,
                venta_reserva__estado_pago__in=['pagado', 'parcial']
            ).values(
                'metodo_pago'
            ).annotate(
                count=Count('id'),
                revenue=Sum('monto')
            )

            # Agrupar por método simplificado
            result = {}
            for stat in stats:
                metodo_original = stat['metodo_pago']
                metodo_simplificado = payment_method_map.get(metodo_original, metodo_original.capitalize())

                if metodo_simplificado not in result:
                    result[metodo_simplificado] = {
                        'count': 0,
                        'revenue': 0
                    }

                result[metodo_simplificado]['count'] += stat['count']
                result[metodo_simplificado]['revenue'] += float(stat['revenue'] or 0)

            return result

        # Obtener stats para cada período
        current_stats = get_payment_stats(date_start, date_stop)
        prev_month_stats = get_payment_stats(prev_month_start, prev_month_stop)
        prev_year_stats = get_payment_stats(prev_year_start, prev_year_stop)

        # Combinar todos los métodos
        all_methods = set(current_stats.keys()) | set(prev_month_stats.keys()) | set(prev_year_stats.keys())

        # Formatear respuesta
        payment_stats = []
        for method in all_methods:
            current = current_stats.get(method, {'count': 0, 'revenue': 0})
            prev_month = prev_month_stats.get(method, {'count': 0, 'revenue': 0})
            prev_year = prev_year_stats.get(method, {'count': 0, 'revenue': 0})

            payment_stats.append({
                'payment_method': method,
                'current_count': current['count'],
                'current_revenue': current['revenue'],
                'previous_month_count': prev_month['count'],
                'previous_month_revenue': prev_month['revenue'],
                'previous_year_count': prev_year['count'],
                'previous_year_revenue': prev_year['revenue']
            })

        # Ordenar por current_revenue descendente
        payment_stats.sort(key=lambda x: x['current_revenue'], reverse=True)

        logger.info(f"aremko-cli: Payment method stats requested for {date_start} to {date_stop}")
        return JsonResponse({
            'success': True,
            'data': payment_stats
        })

    except Exception as e:
        logger.error(f"Error in bookings_by_payment_method: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


def _iso_weeks_range(weeks_count, today=None):
    """Devuelve una lista de (week_start, week_stop, iso_year, iso_week) de las
    ultimas `weeks_count` semanas ISO, ordenada de mas antigua a mas reciente.

    - Semana 0 (la actual): lunes de esta semana → hoy (puede ser miércoles).
    - Semana 1: lunes a domingo completos de la semana anterior.
    - ...

    weekday() devuelve 0 para lunes y 6 para domingo.
    """
    if today is None:
        today = timezone.now().date()
    monday_current = today - timedelta(days=today.weekday())

    weeks = []
    for i in range(weeks_count):
        if i == 0:
            start = monday_current
            stop = today
        else:
            start = monday_current - timedelta(weeks=i)
            stop = start + timedelta(days=6)
        iso_year, iso_week, _ = start.isocalendar()
        weeks.append((start, stop, iso_year, iso_week))

    weeks.reverse()  # más antigua primero, más reciente al final
    return weeks


@csrf_exempt
@require_http_methods(["GET"])
def bookings_weekly_breakdown(request):
    """
    Matriz semanal de reservas: por semana ISO devuelve familia × clientes
    (nuevos / recurrentes / únicos) + revenue y conteo.

    Query params:
        weeks (int, default 12, max 52): cantidad de semanas hacia atras.

    Semana actual termina hoy (aunque sea miércoles). Semanas pasadas son lunes-domingo
    completas. Orden del array: mas antigua → mas reciente (para graficar L→R).

    Definiciones por semana W:
        - new_clients(W)       = clientes cuya PRIMERA venta historica cae en W.
        - returning_clients(W) = clientes con venta en W Y otra venta anterior a inicio de W.
        - unique_clients(W)    = new_clients(W) + returning_clients(W).

    Excluye ventas con estado_pago='cancelado'.
    """
    try:
        try:
            weeks_count = int(request.GET.get('weeks', '12'))
        except (TypeError, ValueError):
            weeks_count = 12
        weeks_count = max(1, min(52, weeks_count))

        today = timezone.now().date()
        weeks = _iso_weeks_range(weeks_count, today=today)
        periodo_start = weeks[0][0]
        periodo_stop = weeks[-1][1]

        # --- 1) Conteo / revenue por (familia, semana) ---
        # Una sola query trae todas las ReservaServicio del periodo con fecha, tipo,
        # precio (con fallback a servicio.precio_base) y cantidad_personas.
        servicios_qs = ReservaServicio.objects.filter(
            venta_reserva__fecha_creacion__date__gte=periodo_start,
            venta_reserva__fecha_creacion__date__lte=periodo_stop,
        ).exclude(
            venta_reserva__estado_pago='cancelado'
        ).values(
            'venta_reserva__fecha_creacion',
            'servicio__tipo_servicio',
            'precio_unitario_venta',
            'servicio__precio_base',
            'cantidad_personas',
        )

        # Inicializar buckets por semana.
        family_buckets = {}  # (week_index) -> {tipo: {'count': N, 'revenue': X}}
        for i in range(len(weeks)):
            family_buckets[i] = {tipo: {'count': 0, 'revenue': 0.0} for tipo in FAMILY_NAMES.keys()}

        def _week_index(d):
            """Devuelve el indice de la semana en `weeks` (o None si fuera de rango)."""
            for idx, (s, e, _y, _w) in enumerate(weeks):
                if s <= d <= e:
                    return idx
            return None

        for row in servicios_qs:
            fc = row['venta_reserva__fecha_creacion']
            d = fc.date() if hasattr(fc, 'date') else fc
            idx = _week_index(d)
            if idx is None:
                continue
            tipo = row['servicio__tipo_servicio'] or 'otro'
            if tipo not in family_buckets[idx]:
                family_buckets[idx][tipo] = {'count': 0, 'revenue': 0.0}
            # Coalesce manual + multiplicacion por cantidad_personas (servicios
            # por persona como tinas y masajes pueden tener cantidad>1).
            precio_unit = row['precio_unitario_venta']
            if precio_unit is None:
                precio_unit = row['servicio__precio_base'] or 0
            cantidad = row['cantidad_personas'] or 1
            family_buckets[idx][tipo]['count'] += 1
            family_buckets[idx][tipo]['revenue'] += float(precio_unit) * cantidad

        # --- 2) Clientes por semana (unicos + nuevos + recurrentes) ---
        # Una query: todas las ventas no canceladas del periodo (cliente_id + fecha).
        ventas_periodo = list(
            VentaReserva.objects.filter(
                fecha_creacion__date__gte=periodo_start,
                fecha_creacion__date__lte=periodo_stop,
            ).exclude(estado_pago='cancelado').values('cliente_id', 'fecha_creacion')
        )

        # Para los clientes que aparecen, calcular su PRIMERA venta historica.
        cliente_ids_periodo = {v['cliente_id'] for v in ventas_periodo if v['cliente_id']}
        primera_venta_por_cliente = {}
        if cliente_ids_periodo:
            qs_primeras = VentaReserva.objects.filter(
                cliente_id__in=cliente_ids_periodo,
            ).exclude(estado_pago='cancelado').values('cliente_id').annotate(
                primera=Min('fecha_creacion__date')
            )
            primera_venta_por_cliente = {p['cliente_id']: p['primera'] for p in qs_primeras}

        # Por cada semana, agrupar clientes.
        clientes_por_semana = [set() for _ in weeks]
        for v in ventas_periodo:
            d = v['fecha_creacion'].date() if hasattr(v['fecha_creacion'], 'date') else v['fecha_creacion']
            idx = _week_index(d)
            if idx is None or not v['cliente_id']:
                continue
            clientes_por_semana[idx].add(v['cliente_id'])

        # --- 3) Armar response ---
        weeks_data = []
        totals = {
            'total_count': 0,
            'total_revenue': 0.0,
            'new_clients_period': 0,
            'returning_clients_period': 0,
        }
        new_per_week = []
        returning_per_week = []

        for idx, (start, stop, iso_year, iso_week) in enumerate(weeks):
            by_family_raw = family_buckets[idx]
            by_family = {}
            week_count = 0
            week_revenue = 0.0
            for tipo, name in FAMILY_NAMES.items():
                stats = by_family_raw.get(tipo, {'count': 0, 'revenue': 0.0})
                by_family[name] = {
                    'count': stats['count'],
                    'revenue': round(stats['revenue'], 2),
                }
                week_count += stats['count']
                week_revenue += stats['revenue']

            clientes_semana = clientes_por_semana[idx]
            unique_count = len(clientes_semana)
            new_count = 0
            for cid in clientes_semana:
                primera = primera_venta_por_cliente.get(cid)
                if primera is not None and start <= primera <= stop:
                    new_count += 1
            returning_count = unique_count - new_count

            weeks_data.append({
                'week_label': f'Sem {iso_week:02d} ({start.isoformat()} al {stop.isoformat()})',
                'iso_year': iso_year,
                'iso_week': iso_week,
                'date_start': start.isoformat(),
                'date_stop': stop.isoformat(),
                'by_family': by_family,
                'total_count': week_count,
                'total_revenue': round(week_revenue, 2),
                'unique_clients': unique_count,
                'new_clients': new_count,
                'returning_clients': returning_count,
            })

            totals['total_count'] += week_count
            totals['total_revenue'] += week_revenue
            totals['new_clients_period'] += new_count
            totals['returning_clients_period'] += returning_count
            new_per_week.append(new_count)
            returning_per_week.append(returning_count)

        # Unique clients en TODO el periodo (sin doble conteo).
        totals['unique_clients_period'] = len(cliente_ids_periodo)
        totals['total_revenue'] = round(totals['total_revenue'], 2)

        # Promedios por semana.
        n = len(weeks)
        averages = {
            'total_count': round(totals['total_count'] / n, 1) if n else 0,
            'total_revenue': round(totals['total_revenue'] / n, 2) if n else 0,
            'unique_clients': round(totals['unique_clients_period'] / n, 1) if n else 0,
            'new_clients': round(totals['new_clients_period'] / n, 1) if n else 0,
            'returning_clients': round(totals['returning_clients_period'] / n, 1) if n else 0,
        }

        # Trend: primeras 4 semanas vs ultimas 4 (si hay >= 8 semanas).
        if n >= 8:
            first4_new = sum(new_per_week[:4]) / 4
            last4_new = sum(new_per_week[-4:]) / 4
            first4_ret = sum(returning_per_week[:4]) / 4
            last4_ret = sum(returning_per_week[-4:]) / 4
        elif n >= 2:
            half = max(1, n // 2)
            first4_new = sum(new_per_week[:half]) / half
            last4_new = sum(new_per_week[-half:]) / half
            first4_ret = sum(returning_per_week[:half]) / half
            last4_ret = sum(returning_per_week[-half:]) / half
        else:
            first4_new = last4_new = first4_ret = last4_ret = 0

        trend = {
            'new_clients_first_4w_avg': round(first4_new, 1),
            'new_clients_last_4w_avg': round(last4_new, 1),
            'returning_clients_first_4w_avg': round(first4_ret, 1),
            'returning_clients_last_4w_avg': round(last4_ret, 1),
        }

        summary = {
            'weeks_count': n,
            'first_week_start': weeks[0][0].isoformat() if weeks else None,
            'last_week_stop': weeks[-1][1].isoformat() if weeks else None,
            'totals': totals,
            'averages_per_week': averages,
            'trend': trend,
        }

        logger.info(
            f"aremko-cli: weekly_breakdown weeks={n} clientes_periodo={totals['unique_clients_period']}"
        )
        return JsonResponse({
            'success': True,
            'data': {
                'weeks': weeks_data,
                'summary': summary,
            }
        })

    except Exception as e:
        logger.error(f"Error in bookings_weekly_breakdown: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def cliente_ficha(request, cliente_id):
    """
    Ficha 360 de un cliente para aremko-cli (dashboards de comercial / recepción).

    Combina VentaReserva (sistema actual) + ServiceHistory (CSV histórico) y
    desglosa el gasto por familia (Tinas/Masajes/Cabañas/Ambientaciones/Otros/Productos).

    Returns:
        {
            "success": true,
            "data": {
                "cliente": {"id": N, "nombre": "...", "telefono": "...", "email": "..."},
                "ficha": {
                    "total": 420000.0,
                    "por_familia": {"Tinas": 180000, "Masajes": 90000, ...},
                    "numero_visitas": 12,
                    "dias_desde_ultima_visita": 23,
                    "tramo_actual": 8,
                    "nivel": "champion",
                    "nunca_compro": ["Ambientaciones"]
                }
            }
        }
    """
    try:
        cliente = Cliente.objects.filter(pk=cliente_id).first()
        if not cliente:
            return JsonResponse({'success': False, 'error': 'Cliente no encontrado'}, status=404)

        ficha = cliente.ficha_360()
        return JsonResponse({
            'success': True,
            'data': {
                'cliente': {
                    'id': cliente.id,
                    'nombre': cliente.nombre,
                    'telefono': cliente.telefono or '',
                    'email': cliente.email or '',
                    'documento_identidad': cliente.documento_identidad or '',
                },
                'ficha': ficha,
            },
        })
    except Exception as e:
        logger.error(f'Error in cliente_ficha: {e}', exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def operating_context(request):
    """
    Devuelve el Contexto Operativo de Aremko en markdown, para inyectar al
    system prompt de análisis IA en aremko-cli.

    Concatena:
    - Sección automática (auto-descubierta del código + BD, cacheada 1h).
    - Sección manual (editable por Jorge desde admin Django).

    Si el caché está vacío o tiene > 1h, se regenera antes de devolver.
    """
    from datetime import timedelta
    from .models import ContextoOperativo
    from .contexto_operativo import regenerar_y_guardar

    try:
        obj = ContextoOperativo.get_solo()
        regenerar = False
        if not obj.seccion_automatica_cache:
            regenerar = True
        elif obj.seccion_automatica_actualizada_en:
            if timezone.now() - obj.seccion_automatica_actualizada_en > timedelta(hours=1):
                regenerar = True
        else:
            regenerar = True

        if regenerar:
            regenerar_y_guardar()
            obj.refresh_from_db()

        partes = []
        if obj.seccion_automatica_cache:
            partes.append(obj.seccion_automatica_cache.strip())
        if obj.seccion_manual:
            partes.append('# Notas Adicionales (sección manual editada por el equipo)\n\n' + obj.seccion_manual.strip())

        contexto = '\n\n'.join(partes).strip()

        return JsonResponse({
            'contexto_markdown': contexto,
            'actualizado_en': obj.seccion_automatica_actualizada_en.isoformat() if obj.seccion_automatica_actualizada_en else None,
            'longitud_caracteres': len(contexto),
        })
    except Exception as e:
        logger.error(f"Error in operating_context: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


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
