"""
Vista para gestionar y eliminar reservas no pagadas de los últimos 30 días.
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Min
from django.utils import timezone
from datetime import timedelta
from ..models import VentaReserva


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def eliminar_reservas_no_pagadas(request):
    """
    Vista para listar reservas no pagadas de los últimos 30 días
    y permitir eliminarlas de forma masiva.
    """
    # Procesar eliminación si es POST
    if request.method == 'POST':
        reservas_ids = request.POST.getlist('reservas_seleccionadas')

        if reservas_ids:
            # Filtrar reservas que efectivamente están pendientes
            reservas_a_eliminar = VentaReserva.objects.filter(
                id__in=reservas_ids,
                estado_pago='pendiente'
            )

            cantidad_eliminadas = reservas_a_eliminar.count()

            # Eliminar las reservas seleccionadas
            reservas_a_eliminar.delete()

            messages.success(
                request,
                f'Se eliminaron {cantidad_eliminadas} reserva(s) no pagada(s) exitosamente.'
            )
        else:
            messages.warning(request, 'No se seleccionaron reservas para eliminar.')

        return redirect('ventas:eliminar_reservas_no_pagadas')

    # Calcular fecha de hace 30 días
    fecha_limite = timezone.now() - timedelta(days=30)

    # Obtener reservas no pagadas de los últimos 30 días
    reservas = VentaReserva.objects.filter(
        estado_pago='pendiente',
        fecha_reserva__gte=fecha_limite
    ).select_related('cliente').prefetch_related('reservaservicios').annotate(
        fecha_primer_servicio=Min('reservaservicios__fecha_agendamiento')
    ).order_by('fecha_reserva')  # De más antigua a más nueva

    # Preparar datos para el template
    reservas_data = []
    for reserva in reservas:
        # Calcular días desde creación
        dias_desde_creacion = (timezone.now() - reserva.fecha_reserva).days

        reservas_data.append({
            'id': reserva.id,
            'fecha_reserva': reserva.fecha_reserva,
            'fecha_checkin': reserva.fecha_primer_servicio,
            'cliente_nombre': reserva.cliente.nombre,
            'cliente_telefono': reserva.cliente.telefono,
            'total': reserva.total,
            'dias_desde_creacion': dias_desde_creacion,
        })

    context = {
        'reservas': reservas_data,
        'total_reservas': len(reservas_data),
        'fecha_limite': fecha_limite,
    }

    return render(request, 'ventas/eliminar_reservas_no_pagadas.html', context)
