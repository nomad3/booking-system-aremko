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

from ..models import VentaReserva, ReservaServicio, ReservaProducto, Pago, Servicio, Producto, Categoria


@staff_member_required
def dashboard_ventas(request):
    """
    Dashboard de VENTAS - Basado en fecha_reserva (cuando se vendió)
    Muestra servicios y productos según cuándo se realizó la venta

    GET /ventas/analytics/dashboard-ventas/

    Parámetros opcionales:
    - year: Año a filtrar (default: 2025)
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
        # Por defecto mostrar datos desde enero 2025
        default_year = 2025 if current_year >= 2024 else current_year
        year = int(request.GET.get('year', default_year))
        month = request.GET.get('month', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        categoria_id = request.GET.get('categoria', None)
    except Exception as e:
        return HttpResponse(f"Error en parámetros: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status=500)

    try:
        # Dashboard de Ventas: Solo incluir ventas PAGADAS (importante para análisis financiero)
        # A diferencia del dashboard operativo, aquí SÍ filtramos por estado_pago='pagado'
        filtro_base = Q(estado_reserva__in=['checkin', 'checkout', 'pendiente']) & Q(estado_pago='pagado')

        # Aplicar filtros de fecha (todo basado en fecha_reserva para dashboard de ventas)
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

        # Obtener categorías disponibles para el filtro
        categorias_disponibles = Categoria.objects.filter(
            servicios__isnull=False
        ).distinct().order_by('nombre')

        # Aplicar filtro de categoría si se seleccionó una
        filtro_categoria = Q()
        categoria_nombre = None
        if categoria_id:
            try:
                categoria = Categoria.objects.get(id=categoria_id)
                filtro_categoria = Q(servicio__categoria_id=categoria_id)
                categoria_nombre = categoria.nombre
                periodo_texto += f" - {categoria.nombre}"
            except Categoria.DoesNotExist:
                pass

        # ====================================================================
        # 1. VENTAS POR FAMILIA DE SERVICIOS (basado en fecha de venta)
        # ====================================================================
        query_servicios_base = ReservaServicio.objects.filter(
            venta_reserva__in=VentaReserva.objects.filter(filtro_base)
        ).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_servicios_base = query_servicios_base.filter(filtro_categoria)

        ventas_por_familia = (
            query_servicios_base
            .values('servicio__categoria__nombre')
            .annotate(
                total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad_servicios=Count('id')
            )
            .order_by('-total_ventas')
        )

        # ====================================================================
        # 2. VENTAS POR SERVICIO INDIVIDUAL (Top 15) - basado en fecha de venta
        # ====================================================================
        query_servicios_individual = ReservaServicio.objects.filter(
            venta_reserva__in=VentaReserva.objects.filter(filtro_base)
        ).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_servicios_individual = query_servicios_individual.filter(filtro_categoria)

        ventas_por_servicio = (
            query_servicios_individual
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
                total_ventas=Sum(F('cantidad') * F('producto__precio_base')),
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
        # 7. RESUMEN GENERAL (Dashboard de Ventas)
        # ====================================================================
        # Todo basado en fecha_reserva - cuando se realizó la venta
        ventas_totales = VentaReserva.objects.filter(filtro_base).aggregate(
            total_ingresos=Sum('total'),
            total_reservas=Count('id')
        )

        # Calcular totales de servicios vendidos (con filtro de categoría si aplica)
        query_total_servicios = ReservaServicio.objects.filter(
            venta_reserva__in=VentaReserva.objects.filter(filtro_base)
        ).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_total_servicios = query_total_servicios.filter(filtro_categoria)

        total_servicios_result = query_total_servicios.aggregate(
            total=Sum(F('servicio__precio_base') * F('cantidad_personas'))
        )
        total_servicios = float(total_servicios_result['total'] or 0)

        # Calcular totales de productos vendidos
        total_productos_result = ReservaProducto.objects.filter(
            venta_reserva__in=VentaReserva.objects.filter(filtro_base)
        ).exclude(producto__isnull=True).aggregate(
            total=Sum(F('cantidad') * F('producto__precio_base'))
        )
        total_productos = float(total_productos_result['total'] or 0)

        # Ticket promedio
        ticket_promedio = 0
        if ventas_totales['total_reservas'] and ventas_totales['total_reservas'] > 0:
            ticket_promedio = float(ventas_totales['total_ingresos'] or 0) / ventas_totales['total_reservas']

        resumen = {
            'total_ingresos': float(ventas_totales['total_ingresos'] or 0),
            'total_reservas': ventas_totales['total_reservas'] or 0,
            'ticket_promedio': ticket_promedio,
            'periodo': periodo_texto,
            'total_servicios': total_servicios,
            'total_productos': total_productos,
            'tipo_dashboard': 'ventas'  # Para identificar en el template
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
            'categoria_id': int(categoria_id) if categoria_id else None,
            'periodo_texto': periodo_texto,

            # Opciones para filtros
            'years_disponibles': range(2020, current_year + 2),
            'meses': [
                {'numero': i, 'nombre': get_month_name(i)}
                for i in range(1, 13)
            ],
            'categorias_disponibles': categorias_disponibles
        }

        return render(request, 'ventas/analytics_dashboard.html', context)
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
def dashboard_operativo(request):
    """
    Dashboard OPERATIVO - Basado en fecha_agendamiento (cuando se prestan los servicios)
    Solo muestra SERVICIOS según cuándo se agendan/prestan
    Excluye productos porque no tienen fecha de consumo

    GET /ventas/analytics/dashboard-operativo/

    Parámetros opcionales:
    - year: Año a filtrar (default: 2025)
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
        # Por defecto mostrar datos desde enero 2025
        default_year = 2025 if current_year >= 2024 else current_year
        year = int(request.GET.get('year', default_year))
        month = request.GET.get('month', None)
        start_date = request.GET.get('start_date', None)
        end_date = request.GET.get('end_date', None)
        categoria_id = request.GET.get('categoria', None)
    except Exception as e:
        return HttpResponse(f"Error en parámetros: {str(e)}<br><pre>{traceback.format_exc()}</pre>", status=500)

    try:
        # Para dashboard operativo: incluir todas las reservas con servicios agendados
        # No filtrar por estado_pago porque queremos ver todos los servicios programados
        # independientemente del estado de pago (importante para planificación operativa)
        ventas_validas = VentaReserva.objects.filter(
            Q(estado_reserva__in=['checkin', 'checkout', 'pendiente', 'confirmada'])
            # Removido filtro de estado_pago para dashboard operativo
        )

        # Construir filtro para servicios basado en fecha_agendamiento
        filtro_servicios = Q()
        if start_date and end_date:
            # Rango personalizado
            filtro_servicios = Q(fecha_agendamiento__gte=start_date, fecha_agendamiento__lte=end_date)
            periodo_texto = f"{start_date} a {end_date}"
        elif month:
            # Mes específico
            filtro_servicios = Q(fecha_agendamiento__year=year, fecha_agendamiento__month=int(month))
            periodo_texto = f"{get_month_name(int(month))} {year}"
        else:
            # Todo el año
            filtro_servicios = Q(fecha_agendamiento__year=year)
            periodo_texto = f"Año {year}"

        # Obtener categorías disponibles para el filtro
        categorias_disponibles = Categoria.objects.filter(
            servicios__isnull=False
        ).distinct().order_by('nombre')

        # Aplicar filtro de categoría si se seleccionó una
        filtro_categoria = Q()
        categoria_nombre = None
        if categoria_id:
            try:
                categoria = Categoria.objects.get(id=categoria_id)
                filtro_categoria = Q(servicio__categoria_id=categoria_id)
                categoria_nombre = categoria.nombre
                periodo_texto += f" - {categoria.nombre}"
            except Categoria.DoesNotExist:
                pass

        # ====================================================================
        # 1. SERVICIOS POR CATEGORÍA (fecha cuando se prestan)
        # ====================================================================
        query_base = ReservaServicio.objects.filter(
            venta_reserva__in=ventas_validas
        ).filter(filtro_servicios).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_base = query_base.filter(filtro_categoria)

        servicios_por_categoria = (
            query_base
            .values('servicio__categoria__nombre')
            .annotate(
                total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad_servicios=Count('id')
            )
            .order_by('-total_ventas')
        )

        # ====================================================================
        # 2. TOP SERVICIOS (fecha cuando se prestan)
        # ====================================================================
        query_top_servicios = ReservaServicio.objects.filter(
            venta_reserva__in=ventas_validas
        ).filter(filtro_servicios).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_top_servicios = query_top_servicios.filter(filtro_categoria)

        top_servicios = (
            query_top_servicios
            .values('servicio__nombre', 'servicio__categoria__nombre')
            .annotate(
                total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad=Count('id')
            )
            .order_by('-total_ventas')[:15]
        )

        # ====================================================================
        # 3. SERVICIOS POR DÍA DE LA SEMANA (cuando se prestan)
        # ====================================================================
        query_servicios_dia = ReservaServicio.objects.filter(
            venta_reserva__in=ventas_validas
        ).filter(filtro_servicios).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_servicios_dia = query_servicios_dia.filter(filtro_categoria)

        servicios_por_dia = (
            query_servicios_dia
            .annotate(dia_semana=ExtractWeekDay('fecha_agendamiento'))
            .values('dia_semana')
            .annotate(
                total_servicios=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad_servicios=Count('id')
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

        servicios_por_dia = [
            {
                'dia': dias_semana.get(item['dia_semana'], 'Desconocido'),
                'total_ventas': float(item['total_servicios'] or 0),
                'cantidad_reservas': item['cantidad_servicios']
            }
            for item in servicios_por_dia
        ]

        # ====================================================================
        # 4. SERVICIOS POR MES (si se ve el año completo)
        # ====================================================================
        servicios_por_mes = []
        if not month:  # Solo si estamos viendo el año completo
            query_servicios_mes = ReservaServicio.objects.filter(
                venta_reserva__in=ventas_validas
            ).filter(fecha_agendamiento__year=year).exclude(servicio__isnull=True)

            if filtro_categoria:
                query_servicios_mes = query_servicios_mes.filter(filtro_categoria)

            servicios_por_mes = (
                query_servicios_mes
                .annotate(mes=TruncMonth('fecha_agendamiento'))
                .values('mes')
                .annotate(
                    total_ventas=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                    cantidad_servicios=Count('id')
                )
                .order_by('mes')
            )

            servicios_por_mes = [
                {
                    'mes': item['mes'].strftime('%B %Y') if item['mes'] else 'Desconocido',
                    'total_ventas': float(item['total_ventas'] or 0),
                    'cantidad_reservas': item['cantidad_servicios']
                }
                for item in servicios_por_mes
            ]

        # ====================================================================
        # 5. RESUMEN OPERATIVO
        # ====================================================================
        # Total de servicios agendados en el período
        query_total_servicios = ReservaServicio.objects.filter(
            venta_reserva__in=ventas_validas
        ).filter(filtro_servicios).exclude(servicio__isnull=True)

        if filtro_categoria:
            query_total_servicios = query_total_servicios.filter(filtro_categoria)

        total_servicios_result = (
            query_total_servicios
            .aggregate(
                total=Sum(F('servicio__precio_base') * F('cantidad_personas')),
                cantidad=Count('id'),
                reservas_unicas=Count('venta_reserva', distinct=True)
            )
        )

        total_servicios = float(total_servicios_result['total'] or 0)
        cantidad_servicios = total_servicios_result['cantidad'] or 0
        reservas_unicas = total_servicios_result['reservas_unicas'] or 0

        # Ticket promedio por servicio
        ticket_promedio = 0
        if cantidad_servicios > 0:
            ticket_promedio = total_servicios / cantidad_servicios

        resumen = {
            'total_ingresos': total_servicios,
            'total_reservas': reservas_unicas,
            'total_servicios_prestados': cantidad_servicios,
            'ticket_promedio': ticket_promedio,
            'periodo': periodo_texto,
            'tipo_dashboard': 'operativo'  # Para identificar en el template
        }

        # ====================================================================
        # 6. PREPARAR DATOS PARA GRÁFICOS
        # ====================================================================
        chart_data = {
            'ventas_familia': [
                {
                    'familia': item['servicio__categoria__nombre'] or 'Sin categoría',
                    'total': float(item['total_ventas'] or 0)
                }
                for item in servicios_por_categoria
            ],
            'ventas_servicio': [
                {
                    'servicio': item['servicio__nombre'],
                    'total': float(item['total_ventas'] or 0)
                }
                for item in top_servicios
            ],
            'ventas_dia_semana': servicios_por_dia,
            'ventas_mes': servicios_por_mes,
            'ventas_forma_pago': [],  # No aplica para dashboard operativo
            'ventas_producto': []  # No aplica para dashboard operativo
        }

        # Contexto para el template
        context = {
            # Datos para gráficos
            'chart_data_json': json.dumps(chart_data),

            # Datos tabulares
            'ventas_por_familia': servicios_por_categoria,
            'ventas_por_servicio': top_servicios,
            'ventas_por_dia_semana': servicios_por_dia,
            'ventas_por_mes': servicios_por_mes if servicios_por_mes else None,

            # Resumen
            'resumen': resumen,

            # Filtros
            'year': int(year),
            'month': int(month) if month else None,
            'start_date': start_date,
            'end_date': end_date,
            'categoria_id': int(categoria_id) if categoria_id else None,
            'periodo_texto': periodo_texto,

            # Opciones para filtros
            'years_disponibles': range(2020, current_year + 2),
            'meses': [
                {'numero': i, 'nombre': get_month_name(i)}
                for i in range(1, 13)
            ],
            'categorias_disponibles': categorias_disponibles
        }

        return render(request, 'ventas/analytics_dashboard_operativo.html', context)
    except Exception as e:
        return HttpResponse(f"<h1>Error 500</h1><p>{str(e)}</p><pre>{traceback.format_exc()}</pre>", status=500)


@staff_member_required
def dashboard_estadisticas(request):
    """
    Función wrapper para mantener compatibilidad con URLs existentes
    Redirige al dashboard de ventas por defecto
    """
    return dashboard_ventas(request)


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
            total_ventas=Sum(F('cantidad') * F('producto__precio_base')),
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
