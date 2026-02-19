"""
Vista para gestión de comandas en cafetería
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count, Sum
from ventas.models import Comanda, DetalleComanda
from datetime import datetime, timedelta

@login_required
def lista_comandas(request):
    """Vista principal del listado de comandas para cafetería"""

    try:
        # Filtros
        estado_filtro = request.GET.get('estado', '')
        fecha_filtro = request.GET.get('fecha', timezone.now().date().isoformat())

    # Query base
    comandas = Comanda.objects.select_related(
        'venta_reserva__cliente',
        'usuario_solicita',
        'usuario_procesa'
    ).prefetch_related(
        'detalles__producto'
    )

    # Aplicar filtros
    if estado_filtro:
        comandas = comandas.filter(estado=estado_filtro)
    else:
        # Por defecto mostrar pendientes y en proceso
        comandas = comandas.filter(estado__in=['pendiente', 'procesando'])

    if fecha_filtro:
        fecha = datetime.strptime(fecha_filtro, '%Y-%m-%d').date()
        comandas = comandas.filter(fecha_solicitud__date=fecha)

    # Ordenar por prioridad: urgentes primero, luego por hora
    comandas = comandas.order_by('-es_urgente', 'fecha_solicitud')

    # Estadísticas del día
    hoy = timezone.now().date()
    stats = {
        'pendientes': Comanda.objects.filter(
            estado='pendiente',
            fecha_solicitud__date=hoy
        ).count(),
        'procesando': Comanda.objects.filter(
            estado='procesando',
            fecha_solicitud__date=hoy
        ).count(),
        'entregadas': Comanda.objects.filter(
            estado='entregada',
            fecha_solicitud__date=hoy
        ).count(),
        'total_hoy': Comanda.objects.filter(
            fecha_solicitud__date=hoy
        ).count()
    }

    context = {
        'comandas': comandas,
        'estado_filtro': estado_filtro,
        'fecha_filtro': fecha_filtro,
        'stats': stats,
        'estados': [
            ('pendiente', 'Pendiente'),
            ('procesando', 'En Proceso'),
            ('entregada', 'Entregada'),
            ('cancelada', 'Cancelada')
        ]
    }

        return render(request, 'control_gestion/comandas/lista.html', context)

    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error en lista_comandas: {str(e)}", exc_info=True)

        # Renderizar una página de error simple
        context = {
            'comandas': [],
            'estado_filtro': '',
            'fecha_filtro': timezone.now().date().isoformat(),
            'stats': {
                'pendientes': 0,
                'procesando': 0,
                'entregadas': 0,
                'total_hoy': 0
            },
            'estados': [
                ('pendiente', 'Pendiente'),
                ('procesando', 'En Proceso'),
                ('entregada', 'Entregada'),
                ('cancelada', 'Cancelada')
            ],
            'error_message': f"Error al cargar comandas: {str(e)}"
        }
        return render(request, 'control_gestion/comandas/lista.html', context)


@login_required
def cambiar_estado_comanda(request, comanda_id):
    """Cambiar el estado de una comanda"""
    if request.method == 'POST':
        comanda = get_object_or_404(Comanda, id=comanda_id)
        nuevo_estado = request.POST.get('estado')

        if nuevo_estado in ['pendiente', 'procesando', 'entregada', 'cancelada']:
            estado_anterior = comanda.estado
            comanda.estado = nuevo_estado

            # Registrar tiempos
            if nuevo_estado == 'procesando':
                comanda.usuario_procesa = request.user
                comanda.fecha_inicio_proceso = timezone.now()
            elif nuevo_estado == 'entregada':
                comanda.fecha_entrega = timezone.now()

            comanda.save()

            messages.success(
                request,
                f'Comanda #{comanda.id} cambió de {estado_anterior} a {nuevo_estado}'
            )

            # Si es AJAX, devolver JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'mensaje': f'Estado actualizado a {comanda.get_estado_display()}'
                })
        else:
            messages.error(request, 'Estado no válido')

    return redirect('control_gestion:lista_comandas')


@login_required
def detalle_comanda(request, comanda_id):
    """Ver detalle completo de una comanda"""
    comanda = get_object_or_404(
        Comanda.objects.select_related(
            'venta_reserva__cliente',
            'usuario_solicita',
            'usuario_procesa'
        ).prefetch_related(
            'detalles__producto'
        ),
        id=comanda_id
    )

    context = {
        'comanda': comanda,
        'puede_procesar': comanda.estado == 'pendiente',
        'puede_entregar': comanda.estado == 'procesando'
    }

    return render(request, 'control_gestion/comandas/detalle.html', context)


@login_required
def comandas_cocina(request):
    """Vista simplificada para pantalla de cocina"""
    # Solo comandas pendientes y en proceso del día
    comandas = Comanda.objects.filter(
        estado__in=['pendiente', 'procesando'],
        fecha_solicitud__date=timezone.now().date()
    ).select_related(
        'venta_reserva__cliente'
    ).prefetch_related(
        'detalles__producto'
    ).order_by('-es_urgente', 'fecha_solicitud')

    context = {
        'comandas': comandas,
        'ahora': timezone.now()
    }

    return render(request, 'control_gestion/comandas/cocina.html', context)


@login_required
def imprimir_comanda(request, comanda_id):
    """Vista para imprimir una comanda"""
    comanda = get_object_or_404(
        Comanda.objects.select_related(
            'venta_reserva__cliente',
            'usuario_solicita'
        ).prefetch_related(
            'detalles__producto'
        ),
        id=comanda_id
    )

    context = {
        'comanda': comanda,
        'fecha_impresion': timezone.now()
    }

    return render(request, 'control_gestion/comandas/imprimir.html', context)