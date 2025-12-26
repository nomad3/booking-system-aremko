"""
Vistas para el sistema de pagos a masajistas
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
import json

from ..models import (
    Proveedor, ReservaServicio, PagoMasajista,
    DetalleServicioPago, VentaReserva
)


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def dashboard_pagos_masajistas(request):
    """
    Dashboard principal del sistema de pagos a masajistas.
    Muestra resumen general y accesos rápidos con filtros.
    """
    from datetime import date
    from django.utils import timezone

    # Obtener lista de masajistas para el filtro
    masajistas = Proveedor.objects.filter(es_masajista=True).order_by('nombre')

    # Buscar si existe Diana para establecerla como predeterminada
    diana = masajistas.filter(nombre__icontains='diana').first()

    # Obtener masajista seleccionado del filtro o usar Diana por defecto
    masajista_id = request.GET.get('masajista')
    if not masajista_id and diana:
        masajista_id = str(diana.id)

    masajista_seleccionado = None
    if masajista_id:
        try:
            masajista_seleccionado = masajistas.get(id=masajista_id)
        except Proveedor.DoesNotExist:
            pass

    # Obtener fechas del filtro o usar el mes actual por defecto
    hoy = date.today()
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    if not fecha_inicio:
        # Primer día del mes actual
        fecha_inicio = hoy.replace(day=1).strftime('%Y-%m-%d')
    if not fecha_fin:
        # Último día del mes actual
        import calendar
        ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
        fecha_fin = hoy.replace(day=ultimo_dia).strftime('%Y-%m-%d')

    # Construir query de servicios pendientes con filtros
    servicios_pendientes = ReservaServicio.objects.filter(
        venta_reserva__estado_pago='pagado',
        pagado_a_proveedor=False,
        proveedor_asignado__es_masajista=True
    )

    # Aplicar filtro de masajista si está seleccionado
    if masajista_seleccionado:
        servicios_pendientes = servicios_pendientes.filter(
            proveedor_asignado=masajista_seleccionado
        )

    # Aplicar filtro de fechas
    if fecha_inicio:
        servicios_pendientes = servicios_pendientes.filter(
            fecha_agendamiento__gte=fecha_inicio
        )
    if fecha_fin:
        servicios_pendientes = servicios_pendientes.filter(
            fecha_agendamiento__lte=fecha_fin
        )

    servicios_pendientes = servicios_pendientes.select_related(
        'servicio', 'proveedor_asignado', 'venta_reserva__cliente'
    ).order_by('fecha_agendamiento', 'hora_inicio')

    # Calcular totales solo para los servicios filtrados
    total_bruto_comisiones = Decimal('0')  # Total bruto para Boleta de Honorarios
    total_pendiente = Decimal('0')  # Total neto a pagar
    servicios_con_montos = []

    for servicio in servicios_pendientes:
        precio_servicio = servicio.calcular_precio()
        if servicio.proveedor_asignado:
            monto_masajista = precio_servicio * (servicio.proveedor_asignado.porcentaje_comision / 100)
            monto_con_retencion = monto_masajista * Decimal('0.855')  # Descuenta 14.5%
            total_bruto_comisiones += monto_masajista  # Suma el total bruto
            total_pendiente += monto_con_retencion

            servicios_con_montos.append({
                'servicio': servicio,
                'precio': precio_servicio,
                'monto_masajista': monto_masajista,
                'monto_neto': monto_con_retencion
            })

    # Últimos pagos (filtrados por masajista si está seleccionado)
    ultimos_pagos = PagoMasajista.objects.select_related('proveedor')
    if masajista_seleccionado:
        ultimos_pagos = ultimos_pagos.filter(proveedor=masajista_seleccionado)
    ultimos_pagos = ultimos_pagos.order_by('-fecha_pago')[:5]

    context = {
        'masajistas': masajistas,
        'masajista_seleccionado': masajista_seleccionado,
        'masajista_id': masajista_id,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'servicios': servicios_con_montos,
        'servicios_pendientes_count': len(servicios_con_montos),
        'total_bruto_comisiones': total_bruto_comisiones,  # Total bruto para Boleta de Honorarios
        'total_pendiente': total_pendiente,
        'ultimos_pagos': ultimos_pagos,
    }

    return render(request, 'ventas/pagos_masajistas/dashboard.html', context)


@staff_required
def listar_servicios_pendientes(request, masajista_id=None):
    """
    Lista los servicios pendientes de pago, filtrados por masajista si se especifica.
    """
    # Filtros
    masajista = None
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Base query
    servicios = ReservaServicio.objects.filter(
        venta_reserva__estado_pago='pagado',
        pagado_a_proveedor=False,
        proveedor_asignado__isnull=False,
        proveedor_asignado__es_masajista=True
    )

    # Filtrar por masajista
    if masajista_id:
        masajista = get_object_or_404(Proveedor, id=masajista_id, es_masajista=True)
        servicios = servicios.filter(proveedor_asignado=masajista)
    elif request.GET.get('masajista'):
        masajista_id = request.GET.get('masajista')
        masajista = get_object_or_404(Proveedor, id=masajista_id, es_masajista=True)
        servicios = servicios.filter(proveedor_asignado=masajista)

    # Filtrar por fechas
    if fecha_inicio:
        servicios = servicios.filter(fecha_agendamiento__gte=fecha_inicio)
    if fecha_fin:
        servicios = servicios.filter(fecha_agendamiento__lte=fecha_fin)

    # Ordenar por fecha
    servicios = servicios.select_related(
        'servicio', 'proveedor_asignado', 'venta_reserva', 'venta_reserva__cliente'
    ).order_by('fecha_agendamiento', 'hora_inicio')

    # Calcular totales
    total_bruto = Decimal('0')
    total_masajista = Decimal('0')
    total_retencion = Decimal('0')
    total_neto = Decimal('0')

    servicios_con_montos = []
    for servicio in servicios:
        precio_servicio = servicio.calcular_precio()
        porcentaje_comision = servicio.proveedor_asignado.porcentaje_comision
        monto_masajista = precio_servicio * (porcentaje_comision / 100)
        monto_retencion = monto_masajista * Decimal('0.145')  # 14.5%
        monto_neto = monto_masajista - monto_retencion

        servicios_con_montos.append({
            'servicio': servicio,
            'precio_servicio': precio_servicio,
            'porcentaje_comision': porcentaje_comision,
            'monto_masajista': monto_masajista,
            'monto_retencion': monto_retencion,
            'monto_neto': monto_neto,
        })

        total_bruto += precio_servicio
        total_masajista += monto_masajista
        total_retencion += monto_retencion
        total_neto += monto_neto

    # Lista de masajistas para el filtro
    masajistas = Proveedor.objects.filter(es_masajista=True).order_by('nombre')

    context = {
        'servicios': servicios_con_montos,
        'masajista': masajista,
        'masajistas': masajistas,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'total_bruto': total_bruto,
        'total_masajista': total_masajista,
        'total_retencion': total_retencion,
        'total_neto': total_neto,
        'cantidad_servicios': len(servicios_con_montos),
    }

    return render(request, 'ventas/pagos_masajistas/servicios_pendientes.html', context)


@staff_required
def registrar_pago(request, masajista_id):
    """
    Registra un nuevo pago para un masajista, incluyendo múltiples servicios.
    """
    masajista = get_object_or_404(Proveedor, id=masajista_id, es_masajista=True)

    if request.method == 'POST':
        # Obtener servicios seleccionados
        servicios_ids = request.POST.getlist('servicios')
        if not servicios_ids:
            messages.error(request, 'Debe seleccionar al menos un servicio.')
            return redirect('ventas:servicios_pendientes_masajista', masajista_id=masajista_id)

        # Obtener servicios
        servicios = ReservaServicio.objects.filter(
            id__in=servicios_ids,
            proveedor_asignado=masajista,
            pagado_a_proveedor=False
        )

        if not servicios.exists():
            messages.error(request, 'No se encontraron servicios válidos para pagar.')
            return redirect('ventas:servicios_pendientes_masajista', masajista_id=masajista_id)

        # Calcular montos
        monto_bruto = Decimal('0')
        for servicio in servicios:
            precio_servicio = servicio.calcular_precio()
            monto_masajista = precio_servicio * (masajista.porcentaje_comision / 100)
            monto_bruto += monto_masajista

        # Crear el pago
        pago = PagoMasajista()
        pago.proveedor = masajista
        pago.periodo_inicio = servicios.order_by('fecha_agendamiento').first().fecha_agendamiento
        pago.periodo_fin = servicios.order_by('fecha_agendamiento').last().fecha_agendamiento
        pago.monto_bruto = monto_bruto
        pago.porcentaje_retencion = Decimal('14.5')
        pago.numero_transferencia = request.POST.get('numero_transferencia', '')
        pago.observaciones = request.POST.get('observaciones', '')
        pago.creado_por = request.user

        # Manejar el comprobante
        if 'comprobante' in request.FILES:
            pago.comprobante = request.FILES['comprobante']

        # Calcular montos y guardar
        pago.calcular_montos()
        pago.save()

        # Crear detalles y marcar servicios como pagados
        for servicio in servicios:
            precio_servicio = servicio.calcular_precio()
            monto_masajista = precio_servicio * (masajista.porcentaje_comision / 100)

            detalle = DetalleServicioPago()
            detalle.pago = pago
            detalle.reserva_servicio = servicio
            detalle.monto_servicio = precio_servicio
            detalle.porcentaje_masajista = masajista.porcentaje_comision
            detalle.monto_masajista = monto_masajista
            detalle.save()

            # Marcar el servicio como pagado
            servicio.pagado_a_proveedor = True
            servicio.pago_proveedor = pago
            servicio.save()

        messages.success(
            request,
            f'Pago registrado exitosamente. '
            f'Monto neto pagado: ${pago.monto_neto:,.0f}'
        )
        return redirect('ventas:dashboard_pagos_masajistas')

    # GET - Mostrar formulario
    servicios_pendientes = masajista.get_servicios_pendientes_pago()

    # Agregar montos calculados a cada servicio
    servicios_con_montos = []
    total_bruto = Decimal('0')
    total_neto = Decimal('0')

    for servicio in servicios_pendientes:
        precio_servicio = servicio.calcular_precio()
        monto_masajista = precio_servicio * (masajista.porcentaje_comision / 100)
        monto_retencion = monto_masajista * Decimal('0.145')
        monto_neto = monto_masajista - monto_retencion

        servicios_con_montos.append({
            'servicio': servicio,
            'precio_servicio': precio_servicio,
            'monto_masajista': monto_masajista,
            'monto_neto': monto_neto,
        })

        total_bruto += monto_masajista
        total_neto += monto_neto

    context = {
        'masajista': masajista,
        'servicios': servicios_con_montos,
        'total_bruto': total_bruto,
        'total_retencion': total_bruto * Decimal('0.145'),
        'total_neto': total_neto,
    }

    return render(request, 'ventas/pagos_masajistas/registrar_pago.html', context)


@staff_required
def historial_pagos(request):
    """
    Muestra el historial de todos los pagos realizados.
    """
    # Filtros
    masajista_id = request.GET.get('masajista')
    fecha_inicio = request.GET.get('fecha_inicio')
    fecha_fin = request.GET.get('fecha_fin')

    # Base query
    pagos = PagoMasajista.objects.all()

    # Aplicar filtros
    if masajista_id:
        pagos = pagos.filter(proveedor_id=masajista_id)

    if fecha_inicio:
        fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d')
        pagos = pagos.filter(fecha_pago__gte=fecha_inicio)

    if fecha_fin:
        fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d')
        fecha_fin = fecha_fin.replace(hour=23, minute=59, second=59)
        pagos = pagos.filter(fecha_pago__lte=fecha_fin)

    # Ordenar y optimizar consultas
    pagos = pagos.select_related('proveedor', 'creado_por').order_by('-fecha_pago')

    # Calcular totales
    totales = pagos.aggregate(
        total_bruto=Sum('monto_bruto'),
        total_retencion=Sum('monto_retencion'),
        total_neto=Sum('monto_neto')
    )

    # Lista de masajistas para el filtro
    masajistas = Proveedor.objects.filter(es_masajista=True).order_by('nombre')

    context = {
        'pagos': pagos,
        'masajistas': masajistas,
        'masajista_id': masajista_id,
        'fecha_inicio': request.GET.get('fecha_inicio'),
        'fecha_fin': request.GET.get('fecha_fin'),
        'totales': totales,
    }

    return render(request, 'ventas/pagos_masajistas/historial_pagos.html', context)


@staff_required
def detalle_pago(request, pago_id):
    """
    Muestra el detalle completo de un pago específico.
    """
    pago = get_object_or_404(PagoMasajista, id=pago_id)
    detalles = pago.detalles.all().select_related(
        'reserva_servicio',
        'reserva_servicio__servicio',
        'reserva_servicio__venta_reserva',
        'reserva_servicio__venta_reserva__cliente'
    )

    context = {
        'pago': pago,
        'detalles': detalles,
    }

    return render(request, 'ventas/pagos_masajistas/detalle_pago.html', context)


@staff_required
def exportar_liquidacion(request, pago_id):
    """
    Exporta la liquidación de un pago en formato Excel.
    """
    import xlwt

    pago = get_object_or_404(PagoMasajista, id=pago_id)
    detalles = pago.detalles.all().select_related(
        'reserva_servicio',
        'reserva_servicio__servicio',
        'reserva_servicio__venta_reserva',
        'reserva_servicio__venta_reserva__cliente'
    )

    # Crear libro Excel
    wb = xlwt.Workbook(encoding='utf-8')
    ws = wb.add_sheet(f'Liquidación {pago.id}')

    # Estilos
    header_style = xlwt.easyxf('font: bold on; align: horiz center')
    date_style = xlwt.easyxf(num_format_str='DD/MM/YYYY')
    money_style = xlwt.easyxf(num_format_str='$#,##0')

    # Encabezado
    row = 0
    ws.write_merge(row, row, 0, 6, f'LIQUIDACIÓN DE PAGO - {pago.proveedor.nombre}', header_style)

    row += 2
    ws.write(row, 0, 'Fecha de Pago:', header_style)
    ws.write(row, 1, pago.fecha_pago, date_style)
    ws.write(row, 3, 'Periodo:', header_style)
    ws.write(row, 4, f'{pago.periodo_inicio.strftime("%d/%m/%Y")} - {pago.periodo_fin.strftime("%d/%m/%Y")}')

    row += 1
    ws.write(row, 0, 'RUT:', header_style)
    ws.write(row, 1, pago.proveedor.rut or 'No registrado')
    ws.write(row, 3, 'Banco:', header_style)
    ws.write(row, 4, pago.proveedor.banco or 'No registrado')

    # Detalle de servicios
    row += 3
    ws.write(row, 0, 'Fecha', header_style)
    ws.write(row, 1, 'Cliente', header_style)
    ws.write(row, 2, 'Servicio', header_style)
    ws.write(row, 3, 'Precio', header_style)
    ws.write(row, 4, '% Comisión', header_style)
    ws.write(row, 5, 'Monto Masajista', header_style)

    row += 1
    for detalle in detalles:
        ws.write(row, 0, detalle.reserva_servicio.fecha_agendamiento, date_style)
        ws.write(row, 1, detalle.reserva_servicio.venta_reserva.cliente.nombre)
        ws.write(row, 2, detalle.reserva_servicio.servicio.nombre)
        ws.write(row, 3, float(detalle.monto_servicio), money_style)
        ws.write(row, 4, f'{detalle.porcentaje_masajista}%')
        ws.write(row, 5, float(detalle.monto_masajista), money_style)
        row += 1

    # Totales
    row += 2
    ws.write(row, 4, 'Monto Bruto:', header_style)
    ws.write(row, 5, float(pago.monto_bruto), money_style)

    row += 1
    ws.write(row, 4, f'Retención ({pago.porcentaje_retencion}%):', header_style)
    ws.write(row, 5, float(pago.monto_retencion), money_style)

    row += 1
    ws.write(row, 4, 'MONTO NETO:', header_style)
    ws.write(row, 5, float(pago.monto_neto), money_style)

    # Configurar anchos de columna
    for i in range(7):
        ws.col(i).width = 4000

    # Respuesta HTTP
    response = HttpResponse(content_type='application/ms-excel')
    response['Content-Disposition'] = f'attachment; filename="liquidacion_pago_{pago.id}.xls"'
    wb.save(response)

    return response