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


# Mapeo tipo_servicio (lowercase singular) → key de salida (lowercase plural sin acento)
# Usado por bookings_monthly_by_family para serializar a un shape estable para gráficos.
FAMILY_KEYS_OUTPUT_MONTHLY = {
    'tina': 'tinas',
    'masaje': 'masajes',
    'cabana': 'cabanas',
    'otro': 'otros',
}

# Labels cortos en español para etiquetas tipo "ene 2025".
# Hard-coded para no depender de locale del sistema.
MES_LABELS_ES = [
    'ene', 'feb', 'mar', 'abr', 'may', 'jun',
    'jul', 'ago', 'sep', 'oct', 'nov', 'dic',
]


@csrf_exempt
@require_http_methods(["GET"])
def bookings_monthly_by_family(request):
    """
    Tendencias mensuales por familia (6-36 meses hacia atrás).

    Query params:
        months (int, default 24, min 1, max 36): número de meses hacia atrás,
            incluyendo el mes en curso. Si months > 36 devuelve 400.

    Response shape (HTTP 200):
        {
          "months": 24,
          "first_month": "2024-06",
          "last_month": "2026-05",
          "data": [
            {
              "month": "2024-06",
              "month_label": "jun 2024",
              "families": {
                "tinas":   {"count": 88, "revenue": 6000000.0},
                "masajes": {"count": 70, "revenue": 2800000.0},
                "cabanas": {"count": 22, "revenue": 1980000.0},
                "otros":   {"count": 5,  "revenue": 200000.0}
              },
              "total": {"count": 185, "revenue": 10980000.0}
            },
            ...
          ],
          "summary_by_family": {
            "tinas":   {total_count, total_revenue, avg_monthly_revenue,
                        best_month, worst_month, trend_slope_pct},
            "masajes": {...}, "cabanas": {...}, "otros": {...}
          }
        }

    Reglas:
    - Revenue = Sum(Coalesce(precio_unitario_venta, servicio__precio_base) * cantidad_personas).
    - Excluye ventas canceladas (estado_pago='cancelado').
    - Meses sin datos se devuelven con count=0 y revenue=0 (continuidad en gráfico).
    - Orden ascendente (mes más viejo primero) — gráfico se dibuja L→R.
    - trend_slope_pct = ((avg_revenue_ultimo_cuarto - avg_revenue_primer_cuarto) /
        avg_revenue_primer_cuarto) * 100, redondeado a 1 decimal. El "cuarto"
        es max(1, N//4) meses. Si el primer cuarto suma 0, devuelve null.
    - statement_timeout local 8000ms.
    """
    try:
        # --- 1) Parsear y validar 'months' ---
        try:
            months_count = int(request.GET.get('months', '24'))
        except (TypeError, ValueError):
            months_count = 24
        if months_count > 36:
            return JsonResponse({'error': 'máximo 36 meses'}, status=400)
        if months_count < 1:
            months_count = 1

        # Imports locales (consistente con otros endpoints de este módulo).
        from calendar import monthrange
        from django.db.models.functions import TruncMonth
        from django.db import connection, transaction

        # --- 2) Construir la lista de meses ascendente ---
        # Último mes = mes en curso. Primer mes = (months_count - 1) meses antes.
        today = timezone.now().date()
        last_y, last_m = today.year, today.month
        months_list = []
        for offset in range(months_count - 1, -1, -1):
            # Aritmética de meses en base 12 para evitar bugs en bordes de año.
            total = (last_y * 12 + (last_m - 1)) - offset
            y = total // 12
            m = (total % 12) + 1
            first_day = _date_cls(y, m, 1)
            last_day = _date_cls(y, m, monthrange(y, m)[1])
            months_list.append((y, m, first_day, last_day))

        periodo_start = months_list[0][2]
        periodo_stop = months_list[-1][3]

        # --- 3) Query agrupada por (mes, tipo_servicio) ---
        stats_by_month_tipo = {}
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Protección contra queries largas (rango de 36 meses).
                try:
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                except Exception:
                    pass  # SQLite en tests no soporta esto.

            servicios_qs = ReservaServicio.objects.filter(
                venta_reserva__fecha_creacion__date__gte=periodo_start,
                venta_reserva__fecha_creacion__date__lte=periodo_stop,
            ).exclude(
                venta_reserva__estado_pago='cancelado',
            ).annotate(
                mes=TruncMonth('venta_reserva__fecha_creacion'),
            ).values('mes', 'servicio__tipo_servicio').annotate(
                count=Count('id'),
                revenue=Sum(
                    Coalesce(F('precio_unitario_venta'), F('servicio__precio_base'))
                    * F('cantidad_personas')
                ),
            )

            for row in servicios_qs:
                mes_val = row['mes']
                if hasattr(mes_val, 'date'):
                    mes_val = mes_val.date()
                if mes_val is None:
                    continue
                y_, m_ = mes_val.year, mes_val.month
                tipo = row['servicio__tipo_servicio'] or 'otro'
                # Cualquier tipo no mapeado cae en 'otro'.
                if tipo not in FAMILY_KEYS_OUTPUT_MONTHLY:
                    tipo = 'otro'
                key = (y_, m_, tipo)
                prev = stats_by_month_tipo.get(key, {'count': 0, 'revenue': 0.0})
                stats_by_month_tipo[key] = {
                    'count': prev['count'] + (row['count'] or 0),
                    'revenue': prev['revenue'] + float(row['revenue'] or 0),
                }

        # --- 4) Armar 'data' ascendente con TODOS los meses (rellena ceros) ---
        data = []
        for (y, m, _fd, _ld) in months_list:
            families_block = {}
            total_count = 0
            total_revenue = 0.0
            for tipo_key, out_key in FAMILY_KEYS_OUTPUT_MONTHLY.items():
                stat = stats_by_month_tipo.get((y, m, tipo_key), {'count': 0, 'revenue': 0.0})
                count_f = stat['count']
                rev_f = stat['revenue']
                families_block[out_key] = {
                    'count': count_f,
                    'revenue': round(rev_f, 2),
                }
                total_count += count_f
                total_revenue += rev_f
            data.append({
                'month': f'{y:04d}-{m:02d}',
                'month_label': f'{MES_LABELS_ES[m - 1]} {y}',
                'families': families_block,
                'total': {
                    'count': total_count,
                    'revenue': round(total_revenue, 2),
                },
            })

        # --- 5) summary_by_family con best/worst/trend ---
        n = len(data)
        quarter = max(1, n // 4)
        summary_by_family = {}
        for tipo_key, out_key in FAMILY_KEYS_OUTPUT_MONTHLY.items():
            revenues = [d['families'][out_key]['revenue'] for d in data]
            counts = [d['families'][out_key]['count'] for d in data]

            total_count_fam = sum(counts)
            total_revenue_fam = sum(revenues)
            avg_monthly_revenue = total_revenue_fam / n if n else 0

            # best/worst month por revenue (en caso de empate gana el más antiguo).
            best_idx = max(range(n), key=lambda i: revenues[i]) if n else 0
            worst_idx = min(range(n), key=lambda i: revenues[i]) if n else 0

            # trend_slope_pct: primer cuarto vs último cuarto.
            avg_first_q = sum(revenues[:quarter]) / quarter
            avg_last_q = sum(revenues[-quarter:]) / quarter
            if avg_first_q == 0:
                trend_slope_pct = None
            else:
                trend_slope_pct = round(((avg_last_q - avg_first_q) / avg_first_q) * 100, 1)

            summary_by_family[out_key] = {
                'total_count': total_count_fam,
                'total_revenue': round(total_revenue_fam, 2),
                'avg_monthly_revenue': round(avg_monthly_revenue, 2),
                'best_month': {
                    'month': data[best_idx]['month'],
                    'revenue': revenues[best_idx],
                },
                'worst_month': {
                    'month': data[worst_idx]['month'],
                    'revenue': revenues[worst_idx],
                },
                'trend_slope_pct': trend_slope_pct,
            }

        response = {
            'months': months_count,
            'first_month': data[0]['month'],
            'last_month': data[-1]['month'],
            'data': data,
            'summary_by_family': summary_by_family,
        }

        logger.info(
            f"aremko-cli: monthly_by_family months={months_count} "
            f"first={response['first_month']} last={response['last_month']}"
        )
        return JsonResponse(response)

    except Exception as e:
        logger.error(f"Error in bookings_monthly_by_family: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def bookings_monthly_by_product(request):
    """
    Tendencias mensuales por producto SKU (6-36 meses hacia atrás).

    Espejo a nivel SKU de bookings_monthly_by_family. La diferencia clave es la
    fórmula de revenue:
        - Servicios:  precio_unitario × cantidad_personas
        - Productos:  precio_unitario × cantidad    ← este endpoint

    Query params:
        months (int, default 24, min 1, max 36): meses hacia atrás incluyendo
            el actual. Si excede 36 retorna 400.
        top (int, opcional): limitar el output a los N productos con mayor
            total_revenue. Si se omite, devuelve todos los productos con ≥1
            venta en el rango.

    Response shape (HTTP 200):
        {
          "months": 24,
          "first_month": "2024-06",
          "last_month":  "2026-05",
          "data": [
            {
              "month": "2024-06",
              "month_label": "jun 2024",
              "products": {
                "<product_id>": {
                  "name": "Crema corporal lavanda 200ml",
                  "count": 12,
                  "revenue": 240000
                },
                ...
              },
              "total": { "count": 50, "revenue": 1200000 }
            },
            ...
          ],
          "summary_by_product": {            # ordenado por total_revenue desc
            "<product_id>": {
              "name": "Crema corporal lavanda 200ml",
              "category": "Aromaterapia",     # (v1.1) str | null
              "total_count": 200,
              "total_revenue": 5000000,
              "avg_monthly_revenue": 208333,
              "best_month":  { "month": "2025-12", "revenue": 480000 },
              "worst_month": { "month": "2025-02", "revenue": 0 },
              "trend_slope_pct": -3.2
            },
            ...
          }
        }

    Reglas:
    - Revenue = Sum(Coalesce(precio_unitario_venta, producto__precio_base) * cantidad).
    - Excluye ventas canceladas (estado_pago='cancelado').
    - Solo se incluyen productos con ≥1 venta en el rango (descarta SKUs descontinuados).
    - En `data[i].products` SE OMITEN los productos sin ventas en ese mes
      (frontend trata la ausencia como 0). Evita matriz 30+ SKUs × 24 meses.
    - `summary_by_product` siempre tiene a TODOS los productos del rango
      (ordenados por total_revenue desc).
    - `category` en summary_by_product: nombre de producto.categoria. null si
      el producto no tiene categoría asignada (FK on_delete=SET_NULL maneja
      huérfanos automáticamente). El frontend agrupa nulls bajo "Sin categoría".
      Solo en summary, NO en data[i].products (estable en el tiempo).
    - trend_slope_pct: misma fórmula que monthly-by-family (primer cuarto vs
      último cuarto). Si <6 meses con datos válidos, retorna null.
    - statement_timeout local 8000ms.
    """
    try:
        # --- 1) Parsear y validar 'months' ---
        try:
            months_count = int(request.GET.get('months', '24'))
        except (TypeError, ValueError):
            months_count = 24
        if months_count > 36:
            return JsonResponse({'error': 'máximo 36 meses'}, status=400)
        if months_count < 1:
            months_count = 1

        # --- 1b) Parsear 'top' opcional ---
        top_raw = request.GET.get('top')
        top_n = None
        if top_raw is not None:
            try:
                top_n = int(top_raw)
                if top_n < 1:
                    top_n = None
            except (TypeError, ValueError):
                top_n = None

        # Imports locales (consistente con otros endpoints de este módulo).
        from calendar import monthrange
        from django.db.models.functions import TruncMonth
        from django.db import connection, transaction

        # Import local de ReservaProducto para evitar ciclo si este módulo se
        # importa antes de que models.py termine de cargar.
        from .models import ReservaProducto

        # --- 2) Construir la lista de meses ascendente ---
        today = timezone.now().date()
        last_y, last_m = today.year, today.month
        months_list = []
        for offset in range(months_count - 1, -1, -1):
            total = (last_y * 12 + (last_m - 1)) - offset
            y = total // 12
            m = (total % 12) + 1
            first_day = _date_cls(y, m, 1)
            last_day = _date_cls(y, m, monthrange(y, m)[1])
            months_list.append((y, m, first_day, last_day))

        periodo_start = months_list[0][2]
        periodo_stop = months_list[-1][3]

        # --- 3) Query agrupada por (mes, producto) ---
        # stats_by_month_product[(y, m, producto_id)] = {'count', 'revenue', 'name'}
        stats_by_month_product = {}
        # Nombres y categorías por producto_id (resolución única — son estables
        # en el tiempo, así no inflamos el payload repitiéndolos por mes).
        product_names = {}
        product_categories = {}  # pid -> str | None (None si sin categoría o huérfana)
        with transaction.atomic():
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                except Exception:
                    pass  # SQLite en tests no soporta esto.

            productos_qs = ReservaProducto.objects.filter(
                venta_reserva__fecha_creacion__date__gte=periodo_start,
                venta_reserva__fecha_creacion__date__lte=periodo_stop,
                producto__isnull=False,
            ).exclude(
                venta_reserva__estado_pago='cancelado',
            ).annotate(
                mes=TruncMonth('venta_reserva__fecha_creacion'),
            ).values(
                'mes', 'producto_id', 'producto__nombre',
                'producto__categoria__nombre',
            ).annotate(
                count=Count('id'),
                revenue=Sum(
                    Coalesce(F('precio_unitario_venta'), F('producto__precio_base'))
                    * F('cantidad')
                ),
            )

            for row in productos_qs:
                mes_val = row['mes']
                if hasattr(mes_val, 'date'):
                    mes_val = mes_val.date()
                if mes_val is None:
                    continue
                y_, m_ = mes_val.year, mes_val.month
                pid = row['producto_id']
                pname = row['producto__nombre'] or f'Producto #{pid}'
                if pid not in product_names:
                    product_names[pid] = pname
                # Categoría: producto.categoria es FK on_delete=SET_NULL, así que
                # el nombre puede venir null sin necesidad de detectar huérfanos
                # explícitamente. Asignamos una sola vez por pid.
                if pid not in product_categories:
                    product_categories[pid] = row['producto__categoria__nombre']

                key = (y_, m_, pid)
                prev = stats_by_month_product.get(key, {'count': 0, 'revenue': 0.0})
                stats_by_month_product[key] = {
                    'count': prev['count'] + (row['count'] or 0),
                    'revenue': prev['revenue'] + float(row['revenue'] or 0),
                }

        # --- 4) Calcular totales por producto para determinar el universo y ordenarlo ---
        # totals_by_product[pid] = {'total_count', 'total_revenue', 'monthly_revenues': [...]}
        totals_by_product = {}
        for pid in product_names:
            monthly_revenues = []
            monthly_counts = []
            for (y, m, _fd, _ld) in months_list:
                stat = stats_by_month_product.get((y, m, pid), {'count': 0, 'revenue': 0.0})
                monthly_revenues.append(stat['revenue'])
                monthly_counts.append(stat['count'])
            totals_by_product[pid] = {
                'total_count': sum(monthly_counts),
                'total_revenue': sum(monthly_revenues),
                'monthly_revenues': monthly_revenues,
                'monthly_counts': monthly_counts,
            }

        # Orden por total_revenue desc (Python preserva insertion order en dicts).
        product_ids_sorted = sorted(
            totals_by_product.keys(),
            key=lambda pid: totals_by_product[pid]['total_revenue'],
            reverse=True,
        )
        if top_n is not None:
            product_ids_sorted = product_ids_sorted[:top_n]
        product_ids_set = set(product_ids_sorted)

        # --- 5) Armar 'data' ascendente. Omitir productos sin ventas en cada mes. ---
        data = []
        for (y, m, _fd, _ld) in months_list:
            products_block = {}
            total_count = 0
            total_revenue = 0.0
            for pid in product_ids_sorted:
                stat = stats_by_month_product.get((y, m, pid))
                if stat is None or (stat['count'] == 0 and stat['revenue'] == 0):
                    continue  # sparse: omitir si no hubo ventas ese mes
                products_block[str(pid)] = {
                    'name': product_names[pid],
                    'count': stat['count'],
                    'revenue': round(stat['revenue'], 2),
                }
                total_count += stat['count']
                total_revenue += stat['revenue']
            data.append({
                'month': f'{y:04d}-{m:02d}',
                'month_label': f'{MES_LABELS_ES[m - 1]} {y}',
                'products': products_block,
                'total': {
                    'count': total_count,
                    'revenue': round(total_revenue, 2),
                },
            })

        # --- 6) summary_by_product con best/worst/trend (ordenado por revenue) ---
        n = len(data)
        quarter = max(1, n // 4)
        summary_by_product = {}
        for pid in product_ids_sorted:
            t = totals_by_product[pid]
            revenues = t['monthly_revenues']

            total_revenue_p = t['total_revenue']
            total_count_p = t['total_count']
            avg_monthly_revenue = total_revenue_p / n if n else 0

            # best/worst month por revenue (empate gana el más antiguo).
            best_idx = max(range(n), key=lambda i: revenues[i]) if n else 0
            worst_idx = min(range(n), key=lambda i: revenues[i]) if n else 0

            # trend_slope_pct: primer cuarto vs último cuarto.
            # Si <6 meses con datos válidos (>0), retornar null como pide el brief.
            meses_con_datos = sum(1 for r in revenues if r > 0)
            if meses_con_datos < 6:
                trend_slope_pct = None
            else:
                avg_first_q = sum(revenues[:quarter]) / quarter
                avg_last_q = sum(revenues[-quarter:]) / quarter
                if avg_first_q == 0:
                    trend_slope_pct = None
                else:
                    trend_slope_pct = round(((avg_last_q - avg_first_q) / avg_first_q) * 100, 1)

            summary_by_product[str(pid)] = {
                'name': product_names[pid],
                'category': product_categories.get(pid),  # str | None
                'total_count': total_count_p,
                'total_revenue': round(total_revenue_p, 2),
                'avg_monthly_revenue': round(avg_monthly_revenue, 2),
                'best_month': {
                    'month': data[best_idx]['month'],
                    'revenue': round(revenues[best_idx], 2),
                },
                'worst_month': {
                    'month': data[worst_idx]['month'],
                    'revenue': round(revenues[worst_idx], 2),
                },
                'trend_slope_pct': trend_slope_pct,
            }

        response = {
            'months': months_count,
            'first_month': data[0]['month'] if data else None,
            'last_month': data[-1]['month'] if data else None,
            'data': data,
            'summary_by_product': summary_by_product,
        }

        logger.info(
            f"aremko-cli: monthly_by_product months={months_count} "
            f"products={len(product_ids_sorted)} top={top_n} "
            f"first={response['first_month']} last={response['last_month']}"
        )
        return JsonResponse(response)

    except Exception as e:
        logger.error(f"Error in bookings_monthly_by_product: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


# Combinaciones explícitas para bookings_family_combinations.
# Cada reserva cae en EXACTAMENTE UNA por su set único de familias core.
# 'otros' agrupa reservas sin familia core (set vacío o sólo 'otros').
COMBO_KEYS_FAMILY = [
    'solo_tinas',
    'solo_masajes',
    'solo_cabanas',
    'tinas_masajes',
    'cabanas_tinas',
    'cabanas_masajes',
    'cabanas_tinas_masajes',
    'otros',
]


def _classify_family_combo(familias_core):
    """Clasifica un set de familias ('tinas'/'masajes'/'cabanas') en una combo key.

    familias_core es un set frozen con SOLO las familias core (sin 'otros').
    """
    if familias_core == {'tinas'}:
        return 'solo_tinas'
    if familias_core == {'masajes'}:
        return 'solo_masajes'
    if familias_core == {'cabanas'}:
        return 'solo_cabanas'
    if familias_core == {'tinas', 'masajes'}:
        return 'tinas_masajes'
    if familias_core == {'cabanas', 'tinas'}:
        return 'cabanas_tinas'
    if familias_core == {'cabanas', 'masajes'}:
        return 'cabanas_masajes'
    if familias_core == {'cabanas', 'tinas', 'masajes'}:
        return 'cabanas_tinas_masajes'
    # set vacío (reservas solo con servicios 'otros' o sin familia core)
    return 'otros'


@csrf_exempt
@require_http_methods(["GET"])
def bookings_family_combinations(request):
    """
    Reservas agrupadas por combinación única de familias (mes a mes, descendente).

    Para medir efectividad de bundling/cross-sell: ¿cuántas reservas son solo
    tinas vs el pack completo cabaña+tina+masaje? Cada VentaReserva cae en
    EXACTAMENTE UNA combinación (set único de familias core, ignorando 'otros').

    Query params:
        months (int, default 24, min 1, max 36): meses hacia atrás incluyendo
            el actual. Si excede, retorna 400.

    Diferencias con monthly-by-family:
        - Agrupa por RESERVA (no por servicio).
        - Orden DESCENDENTE (mes más reciente primero).
        - Revenue por mes incluye todos los servicios de las reservas (incluso
          'otros') para que el total cuadre con lo cobrado.

    Response shape (HTTP 200):
        {
          "months": 24,
          "first_month": "2024-06",      # mes más antiguo del rango
          "last_month":  "2026-05",      # mes más reciente del rango
          "order": "desc",
          "data": [                       # descendente: data[0] = mes actual
            {
              "month": "2026-05",
              "month_label": "may 2026",
              "combinations": {
                "solo_tinas":            {"count_reservas": N, "revenue": X},
                "solo_masajes":          {...}, "solo_cabanas": {...},
                "tinas_masajes":         {...}, "cabanas_tinas": {...},
                "cabanas_masajes":       {...},
                "cabanas_tinas_masajes": {...}, "otros": {...}
              },
              "total": {"count_reservas": N, "revenue": X}
            },
            ...
          ],
          "summary": {
            "total_reservas": N,
            "total_revenue":  X,
            "share_by_combination": {
              "solo_tinas": {"pct_reservas": 38.5, "pct_revenue": 35.2}, ...
            },
            "trend_slope_pct_by_combination": {
              "solo_tinas": 12.5, ...   # % cambio último cuarto vs primer cuarto
            }
          }
        }
    """
    try:
        # --- 1) Parsear/validar 'months' ---
        try:
            months_count = int(request.GET.get('months', '24'))
        except (TypeError, ValueError):
            months_count = 24
        if months_count > 36:
            return JsonResponse({'error': 'máximo 36 meses'}, status=400)
        if months_count < 1:
            months_count = 1

        from calendar import monthrange
        from django.db import connection, transaction

        # --- 2) Lista de meses (la armamos ascendente y luego invertimos al
        #        serializar; así las operaciones cronológicas son naturales) ---
        today = timezone.now().date()
        last_y, last_m = today.year, today.month
        months_list_asc = []
        for offset in range(months_count - 1, -1, -1):
            total = (last_y * 12 + (last_m - 1)) - offset
            y = total // 12
            m = (total % 12) + 1
            first_day = _date_cls(y, m, 1)
            last_day = _date_cls(y, m, monthrange(y, m)[1])
            months_list_asc.append((y, m, first_day, last_day))

        periodo_start = months_list_asc[0][2]
        periodo_stop = months_list_asc[-1][3]

        # --- 3) Una sola query: traer todos los ReservaServicio del rango con
        #        venta_reserva_id + fecha + tipo + precio para clasificar en Python ---
        reservas_data = {}  # vid -> {'y_m': (y,m), 'familias': set, 'revenue': float}
        with transaction.atomic():
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                except Exception:
                    pass  # SQLite en tests no soporta esto.

            servicios_qs = ReservaServicio.objects.filter(
                venta_reserva__fecha_creacion__date__gte=periodo_start,
                venta_reserva__fecha_creacion__date__lte=periodo_stop,
            ).exclude(
                venta_reserva__estado_pago='cancelado',
            ).values(
                'venta_reserva_id',
                'venta_reserva__fecha_creacion',
                'servicio__tipo_servicio',
                'precio_unitario_venta',
                'servicio__precio_base',
                'cantidad_personas',
            )

            for row in servicios_qs:
                vid = row['venta_reserva_id']
                fc = row['venta_reserva__fecha_creacion']
                if fc is None:
                    continue
                fc_date = fc.date() if hasattr(fc, 'date') else fc
                y_m = (fc_date.year, fc_date.month)

                tipo = row['servicio__tipo_servicio'] or 'otro'
                if tipo not in FAMILY_KEYS_OUTPUT_MONTHLY:
                    tipo = 'otro'
                fam_plural = FAMILY_KEYS_OUTPUT_MONTHLY[tipo]  # tinas/masajes/cabanas/otros

                # Coalesce manual + cantidad_personas (mismo criterio que by-family).
                precio_unit = row['precio_unitario_venta']
                if precio_unit is None:
                    precio_unit = row['servicio__precio_base'] or 0
                cantidad = row['cantidad_personas'] or 1
                rev = float(precio_unit) * cantidad

                if vid not in reservas_data:
                    reservas_data[vid] = {
                        'y_m': y_m,
                        'familias': set(),
                        'revenue': 0.0,
                    }
                # Sólo familias core entran al set de clasificación.
                if fam_plural in ('tinas', 'masajes', 'cabanas'):
                    reservas_data[vid]['familias'].add(fam_plural)
                # Revenue suma TODOS los servicios (incluso 'otros') para que
                # el total cuadre con lo cobrado.
                reservas_data[vid]['revenue'] += rev

        # --- 4) Clasificar cada reserva en una combo y bucketear por mes ---
        # buckets[(y, m, combo_key)] = {'count_reservas': N, 'revenue': X}
        buckets = {}
        for vid, d in reservas_data.items():
            y, m = d['y_m']
            combo = _classify_family_combo(d['familias'])
            key = (y, m, combo)
            prev = buckets.get(key, {'count_reservas': 0, 'revenue': 0.0})
            buckets[key] = {
                'count_reservas': prev['count_reservas'] + 1,
                'revenue': prev['revenue'] + d['revenue'],
            }

        # --- 5) Armar 'data' DESCENDENTE (mes actual primero) con todas las combos ---
        months_list_desc = list(reversed(months_list_asc))
        data = []
        for (y, m, _fd, _ld) in months_list_desc:
            combos_block = {}
            total_count = 0
            total_revenue = 0.0
            for combo_key in COMBO_KEYS_FAMILY:
                stat = buckets.get((y, m, combo_key), {'count_reservas': 0, 'revenue': 0.0})
                combos_block[combo_key] = {
                    'count_reservas': stat['count_reservas'],
                    'revenue': round(stat['revenue'], 2),
                }
                total_count += stat['count_reservas']
                total_revenue += stat['revenue']
            data.append({
                'month': f'{y:04d}-{m:02d}',
                'month_label': f'{MES_LABELS_ES[m - 1]} {y}',
                'combinations': combos_block,
                'total': {
                    'count_reservas': total_count,
                    'revenue': round(total_revenue, 2),
                },
            })

        # --- 6) summary: totales, share, trend_slope_pct por combinación ---
        n = len(data)
        quarter = max(1, n // 4)

        total_reservas = sum(d['total']['count_reservas'] for d in data)
        total_revenue = sum(d['total']['revenue'] for d in data)

        share_by_combination = {}
        trend_by_combination = {}
        for combo_key in COMBO_KEYS_FAMILY:
            # Series por mes (en orden descendente igual que data).
            counts_desc = [d['combinations'][combo_key]['count_reservas'] for d in data]
            revs_desc = [d['combinations'][combo_key]['revenue'] for d in data]

            sum_count = sum(counts_desc)
            sum_revenue = sum(revs_desc)
            share_by_combination[combo_key] = {
                'pct_reservas': round((sum_count / total_reservas) * 100, 1) if total_reservas else 0.0,
                'pct_revenue': round((sum_revenue / total_revenue) * 100, 1) if total_revenue else 0.0,
            }

            # Trend: primer cuarto (más viejo) = revs_desc[-quarter:]
            #        último cuarto (más nuevo) = revs_desc[:quarter]
            avg_first_q = sum(revs_desc[-quarter:]) / quarter
            avg_last_q = sum(revs_desc[:quarter]) / quarter
            if avg_first_q == 0:
                trend_by_combination[combo_key] = None
            else:
                trend_by_combination[combo_key] = round(
                    ((avg_last_q - avg_first_q) / avg_first_q) * 100, 1
                )

        # first_month / last_month: rango cronológico (más viejo → más nuevo),
        # independiente del orden de 'data'.
        oldest_y, oldest_m = months_list_asc[0][0], months_list_asc[0][1]
        newest_y, newest_m = months_list_asc[-1][0], months_list_asc[-1][1]

        response = {
            'months': months_count,
            'first_month': f'{oldest_y:04d}-{oldest_m:02d}',
            'last_month': f'{newest_y:04d}-{newest_m:02d}',
            'order': 'desc',
            'data': data,
            'summary': {
                'total_reservas': total_reservas,
                'total_revenue': round(total_revenue, 2),
                'share_by_combination': share_by_combination,
                'trend_slope_pct_by_combination': trend_by_combination,
            },
        }

        logger.info(
            f"aremko-cli: family_combinations months={months_count} "
            f"reservas_total={total_reservas}"
        )
        return JsonResponse(response)

    except Exception as e:
        logger.error(f"Error in bookings_family_combinations: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


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


# ============================================================================
# TAXONOMÍA DE CLIENTES (3 ejes: Valor + Estilo + Contexto)
#
# Consume la tabla ventas_clientetaxonomia poblada por el comando
# recalcular_taxonomia_clientes (cron nocturno). Dos endpoints:
#   - /clientes/taxonomia/segments/ → distribución agregada + matrices cruzadas
#   - /clientes/taxonomia/cohort/   → drill-down por filtros, lista de IDs
# ============================================================================

# Orden canónico para reportes deterministas (idéntico al comando exploratorio).
TAXO_EJE_VALOR_ORDEN = [
    'Campeón', 'Leal', 'Gran Gastador Ocasional', 'Regular',
    'En Prueba', 'En Riesgo', 'Dormido', 'Pre-sistema',
]
TAXO_EJE_ESTILO_ORDEN = [
    'Devoto del Masaje', 'Amante de las Tinas', 'Experiencia Completa',
    'Buscador de Alojamiento', 'Probador Esporádico', 'N/A (pre-sistema)',
]
TAXO_EJE_CONTEXTO_ORDEN = [
    'Pareja Romántica', 'Auto-cuidado Solo', 'Grupo', 'Familiar',
    'Turista Estacional', 'Local Frecuente',
    'Visitante Solo', 'Visitante Pareja', 'Visitante Grupal',
    'Sin clasificar', 'N/A (pre-sistema)',
]
TAXO_PRE_SISTEMA_LABELS = {'Pre-sistema', 'N/A (pre-sistema)'}


@csrf_exempt
@require_http_methods(["GET"])
def clientes_taxonomia_segments(request):
    """
    Distribución agregada de la taxonomía multidimensional.

    Devuelve totales por categoría en cada uno de los 3 ejes + matrices
    cruzadas (Valor × Estilo y Estilo × Contexto) para visualización en
    dashboards. No expone PII — solo conteos.

    Response shape (HTTP 200):
        {
          "total_clientes": 14228,
          "n_sistema_actual": 3897,
          "n_pre_sistema": 10331,
          "ultima_actualizacion": "2026-05-23T03:18:24+00:00",
          "meses_ventana": 24,
          "eje_valor": [
            {"label": "Campeón", "count": 17,
             "pct_total": 0.1, "pct_sistema_actual": 0.4},
            ...
          ],
          "eje_estilo":   [...],
          "eje_contexto": [...],
          "matriz_valor_x_estilo": [
            {"valor": "Campeón", "estilo": "Devoto del Masaje", "count": 5},
            ...   # solo celdas con count > 0
          ],
          "matriz_estilo_x_contexto": [
            {"estilo": "Amante de las Tinas", "contexto": "Visitante Pareja", "count": 1065},
            ...
          ]
        }
    """
    from .models import ClienteTaxonomia
    from django.db.models import Max
    try:
        from django.db import connection, transaction
        with transaction.atomic():
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                except Exception:
                    pass

            # Totales
            total = ClienteTaxonomia.objects.count()
            n_pre = ClienteTaxonomia.objects.filter(eje_valor='Pre-sistema').count()
            n_sa = total - n_pre

            # Última actualización
            ultima = ClienteTaxonomia.objects.aggregate(m=Max('calculado_en'))['m']
            ultima_iso = ultima.isoformat() if ultima else None

            # meses_ventana (asumimos un solo valor, tomamos el más común)
            meses_ventana = (
                ClienteTaxonomia.objects.values_list('meses_ventana', flat=True)
                .first() or 24
            )

            def _build_distribucion(field: str, orden: list) -> list:
                rows = (
                    ClienteTaxonomia.objects.values(field)
                    .annotate(count=Count('id'))
                )
                count_by_label = {r[field]: r['count'] for r in rows}
                result = []
                # En orden canónico
                for label in orden:
                    n = count_by_label.get(label, 0)
                    pct_total = round(n / total * 100, 1) if total else 0.0
                    if label in TAXO_PRE_SISTEMA_LABELS:
                        pct_sa = None  # no aplica
                    else:
                        pct_sa = round(n / n_sa * 100, 1) if n_sa else 0.0
                    result.append({
                        'label': label,
                        'count': n,
                        'pct_total': pct_total,
                        'pct_sistema_actual': pct_sa,
                    })
                # Categorías inesperadas (defensivo)
                for label in set(count_by_label) - set(orden):
                    n = count_by_label[label]
                    pct_total = round(n / total * 100, 1) if total else 0.0
                    pct_sa = round(n / n_sa * 100, 1) if n_sa else 0.0
                    result.append({
                        'label': label,
                        'count': n,
                        'pct_total': pct_total,
                        'pct_sistema_actual': pct_sa,
                    })
                return result

            eje_valor = _build_distribucion('eje_valor', TAXO_EJE_VALOR_ORDEN)
            eje_estilo = _build_distribucion('eje_estilo', TAXO_EJE_ESTILO_ORDEN)
            eje_contexto = _build_distribucion('eje_contexto', TAXO_EJE_CONTEXTO_ORDEN)

            # Matriz Valor × Estilo
            matriz_vs_rows = (
                ClienteTaxonomia.objects.values('eje_valor', 'eje_estilo')
                .annotate(count=Count('id'))
                .order_by('eje_valor', 'eje_estilo')
            )
            matriz_vs = [
                {'valor': r['eje_valor'], 'estilo': r['eje_estilo'], 'count': r['count']}
                for r in matriz_vs_rows if r['count'] > 0
            ]

            # Matriz Estilo × Contexto
            matriz_ec_rows = (
                ClienteTaxonomia.objects.values('eje_estilo', 'eje_contexto')
                .annotate(count=Count('id'))
                .order_by('eje_estilo', 'eje_contexto')
            )
            matriz_ec = [
                {'estilo': r['eje_estilo'], 'contexto': r['eje_contexto'], 'count': r['count']}
                for r in matriz_ec_rows if r['count'] > 0
            ]

        logger.info(
            f"aremko-cli: taxonomia_segments total={total} sistema_actual={n_sa}"
        )
        return JsonResponse({
            'total_clientes': total,
            'n_sistema_actual': n_sa,
            'n_pre_sistema': n_pre,
            'ultima_actualizacion': ultima_iso,
            'meses_ventana': meses_ventana,
            'eje_valor': eje_valor,
            'eje_estilo': eje_estilo,
            'eje_contexto': eje_contexto,
            'matriz_valor_x_estilo': matriz_vs,
            'matriz_estilo_x_contexto': matriz_ec,
        })

    except Exception as e:
        logger.error(f"Error in clientes_taxonomia_segments: {str(e)}", exc_info=True)
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["GET"])
def clientes_taxonomia_cohort(request):
    """
    Drill-down a una cohorte específica filtrando por uno o más ejes.

    Query params (al menos UNO obligatorio):
        eje_valor    (ej: 'Campeón')
        eje_estilo   (ej: 'Devoto del Masaje')
        eje_contexto (ej: 'Visitante Pareja')
        limit        (default 100, max 500)
        order_by     (default 'gasto_total_desc'). Opciones:
                     'gasto_total_desc', 'gasto_total_asc',
                     'visitas_desc', 'antiguedad_desc', 'recency_asc'

    Si no se pasa ningún filtro de eje, retorna 400.

    Response shape (HTTP 200):
        {
          "filtros": {"eje_valor": "Campeón", "eje_estilo": "Devoto del Masaje"},
          "count_total": 5,
          "limit": 100,
          "stats": {
            "gasto_total_sum": 3570000,
            "gasto_total_avg": 714000,
            "total_visitas_avg": 14.6,
            "ticket_promedio_avg": 71000,
            "antiguedad_meses_avg": 30
          },
          "clientes": [
            {
              "cliente_id": 4,
              "eje_valor": "Campeón",
              "eje_estilo": "Devoto del Masaje",
              "eje_contexto": "Visitante Pareja",
              "total_visitas": 48,
              "gasto_total": 1920000,
              "ticket_promedio": 40000,
              "ultima_visita": "2026-05-15",
              "dias_desde_ultima_visita": 8,
              "antiguedad_meses": 66,
              "tiene_historial_pre_sistema": true,
              "avg_cantidad_personas": 1.0,
              "pct_finde": 35.4,
              "pct_reservas_bundle": 12.5
            },
            ...
          ]
        }

    No expone PII (nombre/teléfono/email). Solo cliente_id + features.
    Para acciones sobre los clientes (campañas SMS, etc.) usar el admin
    Django con el ID retornado.
    """
    from .models import ClienteTaxonomia
    from django.db.models import Avg, Sum
    try:
        eje_valor = (request.GET.get('eje_valor') or '').strip() or None
        eje_estilo = (request.GET.get('eje_estilo') or '').strip() or None
        eje_contexto = (request.GET.get('eje_contexto') or '').strip() or None

        # Validación: al menos un filtro debe venir
        if not any([eje_valor, eje_estilo, eje_contexto]):
            return JsonResponse({
                'error': 'Debes pasar al menos uno de: eje_valor, eje_estilo, eje_contexto'
            }, status=400)

        # Validar valores contra el orden canónico (defensivo)
        if eje_valor and eje_valor not in TAXO_EJE_VALOR_ORDEN:
            return JsonResponse({
                'error': f"eje_valor '{eje_valor}' no es válido. "
                         f"Opciones: {TAXO_EJE_VALOR_ORDEN}"
            }, status=400)
        if eje_estilo and eje_estilo not in TAXO_EJE_ESTILO_ORDEN:
            return JsonResponse({
                'error': f"eje_estilo '{eje_estilo}' no es válido. "
                         f"Opciones: {TAXO_EJE_ESTILO_ORDEN}"
            }, status=400)
        if eje_contexto and eje_contexto not in TAXO_EJE_CONTEXTO_ORDEN:
            return JsonResponse({
                'error': f"eje_contexto '{eje_contexto}' no es válido. "
                         f"Opciones: {TAXO_EJE_CONTEXTO_ORDEN}"
            }, status=400)

        # Límite
        try:
            limit = int(request.GET.get('limit', '100'))
        except (TypeError, ValueError):
            limit = 100
        limit = max(1, min(500, limit))

        # Orden
        order_by_param = (request.GET.get('order_by') or 'gasto_total_desc').strip()
        ORDER_MAP = {
            'gasto_total_desc': '-gasto_total',
            'gasto_total_asc': 'gasto_total',
            'visitas_desc': '-total_visitas',
            'antiguedad_desc': '-antiguedad_meses',
            'recency_asc': 'dias_desde_ultima_visita',  # más reciente primero
        }
        order_field = ORDER_MAP.get(order_by_param, '-gasto_total')

        # Filtros
        filtros_dict = {}
        qs = ClienteTaxonomia.objects.all()
        if eje_valor:
            qs = qs.filter(eje_valor=eje_valor)
            filtros_dict['eje_valor'] = eje_valor
        if eje_estilo:
            qs = qs.filter(eje_estilo=eje_estilo)
            filtros_dict['eje_estilo'] = eje_estilo
        if eje_contexto:
            qs = qs.filter(eje_contexto=eje_contexto)
            filtros_dict['eje_contexto'] = eje_contexto

        from django.db import connection, transaction
        with transaction.atomic():
            with connection.cursor() as cursor:
                try:
                    cursor.execute("SET LOCAL statement_timeout = '8s'")
                except Exception:
                    pass

            count_total = qs.count()

            # Stats agregados
            agg = qs.aggregate(
                gasto_total_sum=Sum('gasto_total'),
                gasto_total_avg=Avg('gasto_total'),
                visitas_avg=Avg('total_visitas'),
                ticket_avg=Avg('ticket_promedio'),
                antiguedad_avg=Avg('antiguedad_meses'),
            )
            stats = {
                'gasto_total_sum': int(agg['gasto_total_sum'] or 0),
                'gasto_total_avg': round(agg['gasto_total_avg'] or 0, 0),
                'total_visitas_avg': round(agg['visitas_avg'] or 0, 1),
                'ticket_promedio_avg': round(agg['ticket_avg'] or 0, 0),
                'antiguedad_meses_avg': round(agg['antiguedad_avg'] or 0, 1),
            }

            # Lista limitada
            rows = list(qs.order_by(order_field).values(
                'cliente_id',
                'eje_valor', 'eje_estilo', 'eje_contexto',
                'total_visitas', 'gasto_total', 'ticket_promedio',
                'ultima_visita', 'dias_desde_ultima_visita',
                'antiguedad_meses', 'tiene_historial_pre_sistema',
                'avg_cantidad_personas', 'pct_finde', 'pct_reservas_bundle',
            )[:limit])

            clientes = []
            for r in rows:
                clientes.append({
                    'cliente_id': r['cliente_id'],
                    'eje_valor': r['eje_valor'],
                    'eje_estilo': r['eje_estilo'],
                    'eje_contexto': r['eje_contexto'],
                    'total_visitas': r['total_visitas'],
                    'gasto_total': r['gasto_total'],
                    'ticket_promedio': r['ticket_promedio'],
                    'ultima_visita': r['ultima_visita'].isoformat() if r['ultima_visita'] else None,
                    'dias_desde_ultima_visita': r['dias_desde_ultima_visita'],
                    'antiguedad_meses': r['antiguedad_meses'],
                    'tiene_historial_pre_sistema': r['tiene_historial_pre_sistema'],
                    'avg_cantidad_personas': r['avg_cantidad_personas'],
                    'pct_finde': r['pct_finde'],
                    'pct_reservas_bundle': r['pct_reservas_bundle'],
                })

        logger.info(
            f"aremko-cli: taxonomia_cohort filtros={filtros_dict} "
            f"count={count_total} returned={len(clientes)}"
        )
        return JsonResponse({
            'filtros': filtros_dict,
            'count_total': count_total,
            'limit': limit,
            'order_by': order_by_param,
            'stats': stats,
            'clientes': clientes,
        })

    except Exception as e:
        logger.error(f"Error in clientes_taxonomia_cohort: {str(e)}", exc_info=True)
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
