"""
Vista de calendario tipo matriz para visualizar disponibilidad de servicios
Muestra en filas los horarios/slots y en columnas los recursos disponibles (ej: tinas)
"""

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.db.models import Q, Count, Prefetch
from datetime import datetime, timedelta, date
from django.utils import timezone
from django.contrib import messages
from ..models import (
    Servicio,
    CategoriaServicio,
    ReservaServicio,
    VentaReserva
)
import json


def staff_required(view_func):
    """Decorador para requerir que el usuario sea staff"""
    decorated_view = user_passes_test(lambda u: u.is_staff)(view_func)
    return login_required(decorated_view)


@staff_required
def calendario_matriz_view(request):
    """
    Vista principal del calendario matriz.
    Muestra una matriz de disponibilidad para una categoría y fecha específica.
    """
    # Obtener parámetros de la request
    fecha_str = request.GET.get('fecha', date.today().strftime('%Y-%m-%d'))
    categoria_id = request.GET.get('categoria', '1')  # Default a Tinas (ID=1)

    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_seleccionada = date.today()

    # Obtener todas las categorías para el selector
    categorias = CategoriaServicio.objects.all().order_by('nombre')

    # Obtener la categoría seleccionada
    try:
        categoria = CategoriaServicio.objects.get(id=categoria_id)
    except CategoriaServicio.DoesNotExist:
        categoria = categorias.first()
        categoria_id = categoria.id if categoria else None

    # Obtener servicios de la categoría
    servicios = Servicio.objects.filter(
        categoria=categoria,
        activo=True
    ).order_by('nombre')

    # Generar la matriz de disponibilidad
    matriz_data = generar_matriz_disponibilidad(
        fecha_seleccionada,
        categoria,
        servicios
    )

    # Contexto para el template
    context = {
        'fecha_seleccionada': fecha_seleccionada,
        'fecha_str': fecha_seleccionada.strftime('%Y-%m-%d'),
        'categoria_seleccionada': categoria,
        'categoria_id': categoria_id,
        'categorias': categorias,
        'matriz': matriz_data['matriz'],
        'slots_horarios': matriz_data['slots'],
        'recursos': matriz_data['recursos'],
        'resumen': matriz_data['resumen'],
    }

    # TEMPORAL: Usar template simple para debug en producción
    return render(request, 'ventas/calendario_matriz_simple.html', context)


def generar_matriz_disponibilidad(fecha, categoria, servicios):
    """
    Genera la matriz de disponibilidad para una fecha y categoría.

    Returns:
        dict con:
        - matriz: dict[slot][recurso] = estado
        - slots: lista de horarios disponibles
        - recursos: lista de recursos/servicios
        - resumen: estadísticas de ocupación
    """

    # Obtener todas las reservas del día para esta categoría
    reservas = ReservaServicio.objects.filter(
        fecha_agendamiento=fecha,
        servicio__categoria=categoria,
        venta_reserva__estado_pago__in=['pagado', 'parcial', 'pendiente']
    ).select_related('servicio', 'venta_reserva', 'venta_reserva__cliente')

    # Para Tinas Calientes, asumimos 8 tinas disponibles
    # Para otros servicios, usamos los servicios individuales como recursos
    if categoria.nombre == "Tinas Calientes":
        recursos = [f"Tina {i}" for i in range(1, 9)]  # 8 tinas
        # Generar slots cada 2 horas (duración típica de tina)
        slots = generar_slots_horarios(
            hora_inicio="10:00",
            hora_fin="22:00",
            duracion_minutos=120
        )
    elif categoria.nombre == "Masajes":
        # Para masajes, cada servicio es un recurso diferente
        recursos = [s.nombre for s in servicios]
        # Slots cada hora (duración típica de masaje)
        slots = generar_slots_horarios(
            hora_inicio="09:00",
            hora_fin="21:00",
            duracion_minutos=60
        )
    else:
        # Para alojamientos u otros
        recursos = [s.nombre for s in servicios]
        slots = ["Check-in 15:00", "Check-out 12:00"]  # Simplificado para alojamientos

    # Inicializar matriz (todos disponibles)
    matriz = {}
    for slot in slots:
        matriz[slot] = {}
        for recurso in recursos:
            matriz[slot][recurso] = {
                'estado': 'disponible',
                'reserva': None,
                'cliente': None
            }

    # Marcar las reservas existentes en la matriz
    for reserva in reservas:
        hora_str = reserva.hora_inicio

        # Buscar el slot correspondiente
        slot_encontrado = None
        for slot in slots:
            if hora_str in slot:
                slot_encontrado = slot
                break

        if slot_encontrado:
            # Para tinas, asignar automáticamente a la primera disponible
            if categoria.nombre == "Tinas Calientes":
                for recurso in recursos:
                    if matriz[slot_encontrado][recurso]['estado'] == 'disponible':
                        matriz[slot_encontrado][recurso] = {
                            'estado': 'ocupado',
                            'reserva': reserva,
                            'cliente': reserva.venta_reserva.cliente.nombre if reserva.venta_reserva.cliente else 'Sin cliente',
                            'servicio': reserva.servicio.nombre,
                            'personas': reserva.cantidad_personas,
                            'reserva_id': reserva.venta_reserva.id,
                            'estado_pago': reserva.venta_reserva.estado_pago
                        }
                        break
            else:
                # Para otros servicios, usar el nombre del servicio
                recurso_nombre = reserva.servicio.nombre
                if recurso_nombre in recursos and slot_encontrado in matriz:
                    matriz[slot_encontrado][recurso_nombre] = {
                        'estado': 'ocupado',
                        'reserva': reserva,
                        'cliente': reserva.venta_reserva.cliente.nombre if reserva.venta_reserva.cliente else 'Sin cliente',
                        'servicio': reserva.servicio.nombre,
                        'personas': reserva.cantidad_personas,
                        'reserva_id': reserva.venta_reserva.id,
                        'estado_pago': reserva.venta_reserva.estado_pago
                    }

    # Calcular resumen de ocupación
    total_slots = len(slots) * len(recursos)
    ocupados = sum(
        1 for slot in matriz.values()
        for recurso_data in slot.values()
        if recurso_data['estado'] == 'ocupado'
    )

    resumen = {
        'total_slots': total_slots,
        'ocupados': ocupados,
        'disponibles': total_slots - ocupados,
        'porcentaje_ocupacion': round((ocupados / total_slots * 100) if total_slots > 0 else 0, 1)
    }

    return {
        'matriz': matriz,
        'slots': slots,
        'recursos': recursos,
        'resumen': resumen
    }


def generar_slots_horarios(hora_inicio, hora_fin, duracion_minutos):
    """
    Genera una lista de slots horarios basados en hora de inicio, fin y duración.

    Args:
        hora_inicio: String "HH:MM"
        hora_fin: String "HH:MM"
        duracion_minutos: int

    Returns:
        Lista de strings con los slots horarios
    """
    slots = []

    # Convertir strings a objetos de tiempo
    inicio = datetime.strptime(hora_inicio, "%H:%M")
    fin = datetime.strptime(hora_fin, "%H:%M")

    actual = inicio
    while actual < fin:
        hora_str = actual.strftime("%H:%M")
        siguiente = actual + timedelta(minutes=duracion_minutos)
        hora_fin_str = siguiente.strftime("%H:%M")

        slots.append(f"{hora_str} - {hora_fin_str}")
        actual = siguiente

    return slots


@staff_required
def calendario_matriz_api(request):
    """
    API endpoint para obtener datos de disponibilidad en formato JSON.
    Útil para actualización dinámica sin recargar la página.
    """
    fecha_str = request.GET.get('fecha', date.today().strftime('%Y-%m-%d'))
    categoria_id = request.GET.get('categoria', '1')

    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        return JsonResponse({'error': 'Fecha inválida'}, status=400)

    try:
        categoria = CategoriaServicio.objects.get(id=categoria_id)
    except CategoriaServicio.DoesNotExist:
        return JsonResponse({'error': 'Categoría no encontrada'}, status=404)

    servicios = Servicio.objects.filter(
        categoria=categoria,
        activo=True
    ).order_by('nombre')

    matriz_data = generar_matriz_disponibilidad(
        fecha_seleccionada,
        categoria,
        servicios
    )

    # Convertir la matriz a formato JSON-serializable
    matriz_json = {}
    for slot, recursos_data in matriz_data['matriz'].items():
        matriz_json[slot] = {}
        for recurso, data in recursos_data.items():
            matriz_json[slot][recurso] = {
                'estado': data['estado'],
                'cliente': data.get('cliente'),
                'servicio': data.get('servicio'),
                'personas': data.get('personas'),
                'reserva_id': data.get('reserva_id'),
                'estado_pago': data.get('estado_pago')
            }

    return JsonResponse({
        'matriz': matriz_json,
        'slots': matriz_data['slots'],
        'recursos': matriz_data['recursos'],
        'resumen': matriz_data['resumen'],
        'fecha': fecha_str,
        'categoria': categoria.nombre
    })


@staff_required
def calendario_matriz_reservar(request):
    """
    API endpoint para crear una reserva rápida desde la matriz.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)

    # TODO: Implementar creación rápida de reserva
    # Por ahora redirigir al formulario de reserva normal

    return JsonResponse({
        'mensaje': 'Funcionalidad en desarrollo',
        'redirect': '/admin/ventas/ventareserva/add/'
    })