"""
Vistas para el módulo de Premios y Fidelización
"""
# Importar parche de compatibilidad primero
from . import importlib_compat

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum, F, Value, DecimalField
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.core.management import call_command
from django.db import transaction
from datetime import timedelta
from decimal import Decimal
import io
import sys

from ..models import ClientePremio, Premio, HistorialTramo, Cliente
from ..services.tramo_service import TramoService
from ..services.premio_service import PremioService


@staff_member_required
def premio_dashboard(request):
    """
    Dashboard principal del módulo de premios y fidelización
    """
    # Estadísticas de premios
    stats = {
        'pendientes': ClientePremio.objects.filter(estado='pendiente_aprobacion').count(),
        'aprobados': ClientePremio.objects.filter(estado='aprobado').count(),
        'enviados': ClientePremio.objects.filter(estado='enviado').count(),
        'usados': ClientePremio.objects.filter(estado='usado').count(),
        'expirados': ClientePremio.objects.filter(estado='expirado').count(),
        'total': ClientePremio.objects.count(),
    }

    # Premios por tipo
    premios_por_tipo = Premio.objects.filter(activo=True).annotate(
        cantidad=Count('clientepremio')
    ).values('tipo', 'nombre', 'cantidad')

    # Últimos premios generados
    ultimos_premios = ClientePremio.objects.select_related(
        'cliente', 'premio'
    ).order_by('-fecha_ganado')[:10]

    # Distribución de clientes por tramo (OPTIMIZADO - query única)
    from collections import defaultdict

    tramo_counts = defaultdict(int)

    # Query OPTIMIZADA: calcular gasto total de cada cliente en UNA sola query
    # Combina servicios históricos + ventas actuales usando SUBQUERIES
    clientes_con_gasto = Cliente.objects.annotate(
        # Gasto en servicios históricos (excluyendo fecha genérica 2021-01-01)
        gasto_historico=Coalesce(
            Sum('service_history__price_paid',
                filter=~Q(service_history__service_date='2021-01-01')),
            Value(0, output_field=DecimalField())
        ),
        # Gasto en ventas actuales (estado pagado o parcial)
        gasto_actual=Coalesce(
            Sum('ventareserva__reservaservicio__precio_final',
                filter=Q(ventareserva__estado_pago__in=['pagado', 'parcial'])),
            Value(0, output_field=DecimalField())
        )
    ).annotate(
        # Gasto total = histórico + actual
        gasto_total=F('gasto_historico') + F('gasto_actual')
    ).values('gasto_total')

    # Agrupar clientes por tramo basado en su gasto total
    for cliente_data in clientes_con_gasto:
        gasto_total = float(cliente_data['gasto_total'] or 0)
        tramo_actual = int(gasto_total / 50000)  # Cada tramo = $50,000
        if tramo_actual > 0 and tramo_actual <= 20:
            tramo_counts[tramo_actual] += 1

    # Construir el diccionario de distribución
    distribución_tramos = {}
    for tramo in sorted(tramo_counts.keys()):
        min_gasto, max_gasto = TramoService.obtener_rango_tramo(tramo)
        distribución_tramos[tramo] = {
            'count': tramo_counts[tramo],
            'min_gasto': min_gasto,
            'max_gasto': max_gasto,
        }

    context = {
        'stats': stats,
        'premios_por_tipo': premios_por_tipo,
        'ultimos_premios': ultimos_premios,
        'distribución_tramos': distribución_tramos,
    }

    return render(request, 'ventas/premios/dashboard.html', context)


@staff_member_required
def premios_pendientes(request):
    """
    Lista de premios pendientes de aprobación
    """
    if request.method == 'POST':
        # Procesar aprobación/rechazo
        action = request.POST.get('action')
        premio_ids = request.POST.getlist('premio_ids')

        if not premio_ids:
            messages.warning(request, 'No se seleccionaron premios.')
            return redirect('ventas:premios_pendientes')

        with transaction.atomic():
            premios = ClientePremio.objects.filter(
                id__in=premio_ids,
                estado='pendiente_aprobacion'
            )

            if action == 'aprobar':
                count = premios.update(
                    estado='aprobado',
                    fecha_aprobacion=timezone.now()
                )
                messages.success(request, f'✅ {count} premio(s) aprobado(s) exitosamente.')

            elif action == 'rechazar':
                count = premios.update(
                    estado='cancelado',
                    fecha_aprobacion=timezone.now()
                )
                messages.warning(request, f'❌ {count} premio(s) cancelado(s).')

        return redirect('ventas:premios_pendientes')

    # GET: Mostrar lista
    premios_pendientes = ClientePremio.objects.filter(
        estado='pendiente_aprobacion'
    ).select_related('cliente', 'premio').order_by('-fecha_ganado')

    context = {
        'premios_pendientes': premios_pendientes,
    }

    return render(request, 'ventas/premios/pendientes.html', context)


@staff_member_required
def clientes_con_premios(request):
    """
    Lista de todos los clientes que tienen premios
    """
    # Filtros
    estado_filter = request.GET.get('estado', '')
    tipo_filter = request.GET.get('tipo', '')

    # Query base
    premios = ClientePremio.objects.select_related('cliente', 'premio').order_by('-fecha_ganado')

    if estado_filter:
        premios = premios.filter(estado=estado_filter)

    if tipo_filter:
        premios = premios.filter(premio__tipo=tipo_filter)

    # Obtener opciones para filtros
    estados = ClientePremio.ESTADO_CHOICES
    tipos = Premio.TIPO_CHOICES

    context = {
        'premios': premios,
        'estados': estados,
        'tipos': tipos,
        'estado_filter': estado_filter,
        'tipo_filter': tipo_filter,
    }

    return render(request, 'ventas/premios/clientes_con_premios.html', context)


@staff_member_required
def historial_tramos(request):
    """
    Vista del historial de cambios de tramos
    """
    # Filtro por cliente
    cliente_id = request.GET.get('cliente')

    if cliente_id:
        historial = HistorialTramo.objects.filter(
            cliente_id=cliente_id
        ).select_related('cliente', 'premio_generado').order_by('-fecha_cambio')

        cliente = get_object_or_404(Cliente, id=cliente_id)
    else:
        # Mostrar últimos cambios de todos los clientes
        historial = HistorialTramo.objects.select_related(
            'cliente', 'premio_generado'
        ).order_by('-fecha_cambio')[:100]
        cliente = None

    # Lista de clientes para el filtro
    clientes_con_historial = Cliente.objects.filter(
        historial_tramos__isnull=False
    ).distinct().order_by('nombre')

    context = {
        'historial': historial,
        'cliente': cliente,
        'clientes_con_historial': clientes_con_historial,
    }

    return render(request, 'ventas/premios/historial_tramos.html', context)


@staff_member_required
def configurar_premios(request):
    """
    Vista para gestionar la configuración de premios disponibles
    """
    premios = Premio.objects.all().annotate(
        total_asignados=Count('clientepremio'),
        total_usados=Count('clientepremio', filter=Q(clientepremio__estado='usado'))
    ).order_by('-activo', 'tipo')

    context = {
        'premios': premios,
    }

    return render(request, 'ventas/premios/configurar.html', context)


@staff_member_required
def procesar_premios_manual(request):
    """
    Ejecuta el comando de procesamiento de premios manualmente
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        # Capturar la salida del comando
        output = io.StringIO()
        sys.stdout = output

        # Ejecutar comando sin dry-run
        call_command('procesar_premios_bienvenida')

        # Restaurar stdout
        sys.stdout = sys.__stdout__

        # Obtener salida
        command_output = output.getvalue()

        messages.success(request, '✅ Procesamiento de premios ejecutado exitosamente.')

        return JsonResponse({
            'success': True,
            'message': 'Premios procesados exitosamente',
            'output': command_output
        })

    except Exception as e:
        sys.stdout = sys.__stdout__
        messages.error(request, f'❌ Error al procesar premios: {str(e)}')

        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
def cliente_premio_detalle(request, premio_id):
    """
    Detalle de un premio específico de un cliente
    """
    cliente_premio = get_object_or_404(
        ClientePremio.objects.select_related('cliente', 'premio'),
        id=premio_id
    )

    # Historial de tramos del cliente
    historial = HistorialTramo.objects.filter(
        cliente=cliente_premio.cliente
    ).order_by('-fecha_cambio')[:10]

    # Otros premios del mismo cliente
    otros_premios = ClientePremio.objects.filter(
        cliente=cliente_premio.cliente
    ).exclude(id=premio_id).select_related('premio').order_by('-fecha_ganado')

    context = {
        'cliente_premio': cliente_premio,
        'historial': historial,
        'otros_premios': otros_premios,
    }

    return render(request, 'ventas/premios/detalle.html', context)


@staff_member_required
def marcar_premio_enviado(request, premio_id):
    """
    Marca un premio como enviado (email enviado al cliente)
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método no permitido'}, status=405)

    try:
        cliente_premio = get_object_or_404(ClientePremio, id=premio_id)

        if cliente_premio.estado != 'aprobado':
            return JsonResponse({
                'success': False,
                'error': 'Solo se pueden marcar como enviados los premios aprobados'
            }, status=400)

        cliente_premio.estado = 'enviado'
        cliente_premio.fecha_enviado = timezone.now()
        cliente_premio.save(update_fields=['estado', 'fecha_enviado'])

        messages.success(request, f'✅ Premio marcado como enviado a {cliente_premio.cliente.nombre}')

        return JsonResponse({
            'success': True,
            'message': 'Premio marcado como enviado'
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@staff_member_required
def estadisticas_premios(request):
    """
    Vista con estadísticas detalladas del programa de fidelización
    """
    # Premios por mes (últimos 12 meses)
    desde = timezone.now() - timedelta(days=365)
    premios_por_mes = ClientePremio.objects.filter(
        fecha_ganado__gte=desde
    ).extra(
        select={'mes': "DATE_TRUNC('month', fecha_ganado)"}
    ).values('mes').annotate(
        cantidad=Count('id')
    ).order_by('mes')

    # Tasa de conversión de premios
    total_premios = ClientePremio.objects.count()
    premios_usados = ClientePremio.objects.filter(estado='usado').count()
    tasa_conversion = (premios_usados / total_premios * 100) if total_premios > 0 else 0

    # Clientes por tramo (OPTIMIZADO - query única)
    from collections import defaultdict
    from django.db.models import F, Sum, Case, When, Value, DecimalField
    from django.db.models.functions import Coalesce

    tramo_counts = defaultdict(int)

    # Query OPTIMIZADA: calcular gasto total de cada cliente en UNA sola query
    clientes_con_gasto = Cliente.objects.annotate(
        gasto_historico=Coalesce(
            Sum('service_history__price_paid',
                filter=~Q(service_history__service_date='2021-01-01')),
            Value(0, output_field=DecimalField())
        ),
        gasto_actual=Coalesce(
            Sum('ventareserva__reservaservicio__precio_final',
                filter=Q(ventareserva__estado_pago__in=['pagado', 'parcial'])),
            Value(0, output_field=DecimalField())
        )
    ).annotate(
        gasto_total=F('gasto_historico') + F('gasto_actual')
    ).values('gasto_total')

    # Agrupar por tramo
    for cliente_data in clientes_con_gasto:
        gasto_total = float(cliente_data['gasto_total'] or 0)
        tramo_actual = int(gasto_total / 50000)
        if tramo_actual > 0 and tramo_actual <= 20:
            tramo_counts[tramo_actual] += 1

    # Construir la lista de clientes por tramo
    clientes_por_tramo = []
    for tramo in sorted(tramo_counts.keys()):
        clientes_por_tramo.append({'tramo': tramo, 'count': tramo_counts[tramo]})

    # Premios más populares
    premios_populares = Premio.objects.annotate(
        total=Count('clientepremio'),
        usados=Count('clientepremio', filter=Q(clientepremio__estado='usado'))
    ).order_by('-total')[:5]

    context = {
        'premios_por_mes': list(premios_por_mes),
        'tasa_conversion': round(tasa_conversion, 1),
        'total_premios': total_premios,
        'premios_usados': premios_usados,
        'clientes_por_tramo': clientes_por_tramo,
        'premios_populares': premios_populares,
    }

    return render(request, 'ventas/premios/estadisticas.html', context)
