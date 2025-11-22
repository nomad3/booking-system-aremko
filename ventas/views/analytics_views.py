# -*- coding: utf-8 -*-
"""
Vistas de Analytics y Estadísticas para Aremko
Proporciona dashboards con métricas de ventas, servicios y productos
"""

from django.shortcuts import render
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, Q, F, Value, CharField
from django.db.models.functions import TruncMonth, TruncDate, ExtractWeekDay
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from ..models import VentaReserva, ReservaServicio, ReservaProducto, Pago, Servicio, Producto


# @staff_member_required  # Temporalmente deshabilitado para debugging
def dashboard_estadisticas(request):
    """
    Dashboard principal de estadísticas con filtros por año/mes

    GET /ventas/analytics/dashboard/

    Parámetros opcionales:
    - year: Año a filtrar (default: año actual)
    - month: Mes a filtrar (1-12, default: todos los meses)
    - start_date: Fecha inicio (YYYY-MM-DD)
    - end_date: Fecha fin (YYYY-MM-DD)
    """
    from django.http import HttpResponse
    import traceback

    try:
        import logging
        logger = logging.getLogger(__name__)

        # Obtener parámetros de filtro
        current_year = timezone.now().year
        year = int(request.GET.get('year', current_year))
        month = request.GET.get('month', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
    except Exception as e:
        return HttpResponse(f"Error en parámetros: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status=500)

    try:
        # Construir filtro base
        filtro_base = Q(estado_reserva__in=['checkin', 'checkout', 'pendiente']) & Q(estado_pago='pagado')

        # Aplicar filtros de fecha
        if start_date and end_date:
            # Rango personalizado
            filtro_base &= Q(fecha_reserva__gte=start_date, fecha_reserva__lte=end_date)
            periodo_texto = f"{start_date} a {end_date}"
        elif month:
            # Mes específico
            filtro_base &= Q(fecha_reserva__year=year, fecha_reserva__month=int(month))
            periodo_texto = f"{get_month_name(int(month))} {year}"
        else:
            # Todo el año
            filtro_base &= Q(fecha_reserva__year=year)
            periodo_texto = f"Año {year}"

        # ====================================================================
        # 1. VENTAS POR FAMILIA DE SERVICIOS
        # ====================================================================
        ventas_por_familia = (
            ReservaServicio.objects
            .filter(venta_reserva__in=VentaReserva.objects.filter(filtro_base))
            .exclude(servicio__isnull=True)
            .values('servicio__categoria__nombre')
            .annotate(
                total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad_servicios=Count('id')
            )
            .order_by('-total_ventas')
        )

        # ====================================================================
        # 2. VENTAS POR SERVICIO INDIVIDUAL (Top 15)
        # ====================================================================
        ventas_por_servicio = (
            ReservaServicio.objects
            .filter(venta_reserva__in=VentaReserva.objects.filter(filtro_base))
            .exclude(servicio__isnull=True)
            .values('servicio__nombre', 'servicio__categoria__nombre')
            .annotate(
                total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad=Count('id')
            )
            .order_by('-total_ventas')[:15]
        )

        # ====================================================================
        # 3. VENTAS POR PRODUCTO (Top 15)
        # ====================================================================
        ventas_por_producto = (
            ReservaProducto.objects
            .filter(venta_reserva__in=VentaReserva.objects.filter(filtro_base))
            .exclude(producto__isnull=True)
            .values('producto__nombre')
            .annotate(
                total_ventas=Sum(F('cantidad') * F('precio_unitario')),
                cantidad_vendida=Sum('cantidad')
            )
            .order_by('-total_ventas')[:15]
        )

        # ====================================================================
        # 4. VENTAS POR DÍA DE LA SEMANA
        # ====================================================================
        ventas_por_dia_semana = (
            VentaReserva.objects
            .filter(filtro_base)
            .annotate(dia_semana=ExtractWeekDay('fecha_reserva'))
            .values('dia_semana')
            .annotate(
                total_ventas=Sum('total'),
                cantidad_reservas=Count('id')
            )
            .order_by('dia_semana')
        )

        # Mapear números a nombres de días
        dias_semana = {
            1: 'Domingo',
            2: 'Lunes',
            3: 'Martes',
            4: 'Miércoles',
            5: 'Jueves',
            6: 'Viernes',
            7: 'Sábado'
        }

        ventas_por_dia_semana = [
            {
                'dia': dias_semana.get(item['dia_semana'], 'Desconocido'),
                'total_ventas': float(item['total_ventas'] or 0),
                'cantidad_reservas': item['cantidad_reservas']
            }
            for item in ventas_por_dia_semana
        ]

        # ====================================================================
        # 5. VENTAS POR MES (Todo el año)
        # ====================================================================
        if not month:  # Solo si estamos viendo el año completo
            ventas_por_mes = (
                VentaReserva.objects
                .filter(Q(fecha_reserva__year=year) & Q(estado_pago='pagado'))
                .annotate(mes=TruncMonth('fecha_reserva'))
                .values('mes')
                .annotate(
                    total_ventas=Sum('total'),
                    cantidad_reservas=Count('id')
                )
                .order_by('mes')
            )

            ventas_por_mes = [
                {
                    'mes': item['mes'].strftime('%B'),
                    'mes_numero': item['mes'].month,
                    'total_ventas': float(item['total_ventas'] or 0),
                    'cantidad_reservas': item['cantidad_reservas']
                }
                for item in ventas_por_mes
            ]
        else:
            ventas_por_mes = []

        # ====================================================================
        # 6. VENTAS POR FORMA DE PAGO
        # ====================================================================
        ventas_por_forma_pago = (
            Pago.objects
            .filter(venta_reserva__in=VentaReserva.objects.filter(filtro_base))
            .values('metodo_pago')
            .annotate(
                total_pagos=Sum('monto'),
                cantidad_transacciones=Count('id')
            )
            .order_by('-total_pagos')
        )

        # Mapear códigos a nombres legibles
        metodos_pago_nombres = {
            'efectivo': 'Efectivo',
            'transferencia': 'Transferencia',
            'flow': 'Flow (Tarjetas)',
            'mercadopago': 'MercadoPago',
            'webpay': 'Webpay',
            'debito': 'Débito',
            'credito': 'Crédito'
        }

        ventas_por_forma_pago = [
            {
                'metodo': metodos_pago_nombres.get(item['metodo_pago'], item['metodo_pago']),
                'total_pagos': float(item['total_pagos'] or 0),
                'cantidad_transacciones': item['cantidad_transacciones']
            }
            for item in ventas_por_forma_pago
        ]

        # ====================================================================
        # 7. RESUMEN GENERAL
        # ====================================================================
        ventas_totales = VentaReserva.objects.filter(filtro_base).aggregate(
            total_ingresos=Sum('total'),
            total_reservas=Count('id')
        )

        # Ticket promedio
        ticket_promedio = 0
        if ventas_totales['total_reservas'] and ventas_totales['total_reservas'] > 0:
            ticket_promedio = float(ventas_totales['total_ingresos'] or 0) / ventas_totales['total_reservas']

        resumen = {
            'total_ingresos': float(ventas_totales['total_ingresos'] or 0),
            'total_reservas': ventas_totales['total_reservas'] or 0,
            'ticket_promedio': ticket_promedio,
            'periodo': periodo_texto
        }

        # ====================================================================
        # 8. PREPARAR DATOS PARA GRÁFICOS (JSON)
        # ====================================================================

        # Convertir QuerySets a listas para JSON
        def queryset_to_list(qs, fields_map):
            """Convierte QuerySet a lista con campos mapeados"""
            result = []
            for item in qs:
                mapped_item = {}
                for db_field, json_field in fields_map.items():
                    value = item.get(db_field)
                    # Convertir Decimal a float
                    if isinstance(value, Decimal):
                        value = float(value)
                    # Convertir None a 0 o string vacío según el tipo esperado
                    elif value is None:
                        value = 0 if 'total' in json_field or 'cantidad' in json_field else ''
                    # Asegurar que sea serializable a JSON
                    elif not isinstance(value, (str, int, float, bool)):
                        value = str(value)
                    mapped_item[json_field] = value
                result.append(mapped_item)
            return result

        # Datos para gráficos
        chart_data = {
            'ventas_familia': queryset_to_list(ventas_por_familia, {
                'servicio__categoria__nombre': 'familia',
                'total_ventas': 'total',
                'cantidad_servicios': 'cantidad'
            }),
            'ventas_servicio': queryset_to_list(ventas_por_servicio, {
                'servicio__nombre': 'servicio',
                'total_ventas': 'total',
                'cantidad': 'cantidad'
            }),
            'ventas_producto': queryset_to_list(ventas_por_producto, {
                'producto__nombre': 'producto',
                'total_ventas': 'total',
                'cantidad_vendida': 'cantidad'
            }),
            'ventas_dia_semana': ventas_por_dia_semana,
            'ventas_mes': ventas_por_mes,
            'ventas_forma_pago': ventas_por_forma_pago
        }

        # ====================================================================
        # CONTEXT
        # ====================================================================
        context = {
            'resumen': resumen,
            'ventas_por_familia': ventas_por_familia,
            'ventas_por_servicio': ventas_por_servicio,
            'ventas_por_producto': ventas_por_producto,
            'ventas_por_dia_semana': ventas_por_dia_semana,
            'ventas_por_mes': ventas_por_mes,
            'ventas_por_forma_pago': ventas_por_forma_pago,
            'chart_data_json': json.dumps(chart_data),

            # Filtros actuales
            'year': year,
            'month': int(month) if month else None,
            'start_date': start_date,
            'end_date': end_date,
            'periodo_texto': periodo_texto,

            # Opciones para filtros
            'years_disponibles': range(2020, current_year + 2),
            'meses': [
                {'numero': i, 'nombre': get_month_name(i)}
                for i in range(1, 13)
            ]
        }

        # return render(request, 'ventas/analytics_dashboard.html', context)
        return render(request, 'ventas/analytics_dashboard_simple.html', context)  # DEBUG
    except Exception as e:
        return HttpResponse(f"<h1>Error 500</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>", status=500)


def get_month_name(month_number):
    """Retorna nombre del mes en español"""
    meses = {
        1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril',
        5: 'Mayo', 6: 'Junio', 7: 'Julio', 8: 'Agosto',
        9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
    }
    return meses.get(month_number, 'Desconocido')


@staff_member_required
def exportar_estadisticas_csv(request):
    """
    Exporta estadísticas a CSV

    GET /ventas/analytics/export-csv/?year=2025&month=11
    """
    import csv
    from django.http import HttpResponse

    # Obtener los mismos filtros que el dashboard
    year = int(request.GET.get('year', timezone.now().year))
    month = request.GET.get('month', None)

    # Construir query (mismo que dashboard)
    filtro_base = Q(estado_reserva__in=['checkin', 'checkout', 'pendiente']) & Q(estado_pago='pagado')

    if month:
        filtro_base &= Q(fecha_reserva__year=year, fecha_reserva__month=int(month))
        filename = f"aremko_estadisticas_{year}_{int(month):02d}.csv"
    else:
        filtro_base &= Q(fecha_reserva__year=year)
        filename = f"aremko_estadisticas_{year}.csv"

    # Crear response CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')  # BOM para Excel

    writer = csv.writer(response)

    # Header
    writer.writerow(['ESTADÍSTICAS AREMKO'])
    writer.writerow(['Periodo', f"{get_month_name(int(month)) if month else 'Año'} {year}"])
    writer.writerow([])

    # Ventas por servicio
    writer.writerow(['VENTAS POR SERVICIO'])
    writer.writerow(['Servicio', 'Categoría', 'Total Ventas', 'Cantidad'])

    ventas_servicio = (
        ReservaServicio.objects
        .filter(venta_reserva__in=VentaReserva.objects.filter(filtro_base))
        .exclude(servicio__isnull=True)
        .values('servicio__nombre', 'servicio__categoria__nombre')
        .annotate(
            total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
            cantidad=Count('id')
        )
        .order_by('-total_ventas')
    )

    for item in ventas_servicio:
        writer.writerow([
            item['servicio__nombre'],
            item['servicio__categoria__nombre'] or 'Sin categoría',
            f"${item['total_ventas']:,.0f}",
            item['cantidad']
        ])

    writer.writerow([])

    # Ventas por producto
    writer.writerow(['VENTAS POR PRODUCTO'])
    writer.writerow(['Producto', 'Total Ventas', 'Cantidad Vendida'])

    ventas_producto = (
        ReservaProducto.objects
        .filter(venta_reserva__in=VentaReserva.objects.filter(filtro_base))
        .exclude(producto__isnull=True)
        .values('producto__nombre')
        .annotate(
            total_ventas=Sum(F('cantidad') * F('precio_unitario')),
            cantidad_vendida=Sum('cantidad')
        )
        .order_by('-total_ventas')
    )

    for item in ventas_producto:
        writer.writerow([
            item['producto__nombre'],
            f"${item['total_ventas']:,.0f}",
            item['cantidad_vendida']
        ])

    return response
