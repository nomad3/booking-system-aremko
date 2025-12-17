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

    # Obtener todas las categorías para el selector
    categorias = CategoriaServicio.objects.all().order_by('nombre')

    # Buscar la categoría "Tinas Calientes" para usarla como default
    # Primero intentar coincidencia exacta, luego parcial
    tinas_categoria = categorias.filter(nombre='Tinas Calientes').first()
    if not tinas_categoria:
        tinas_categoria = categorias.filter(nombre__icontains='tina').exclude(nombre__icontains='empresarial').first()
    if not tinas_categoria:
        tinas_categoria = categorias.filter(nombre__icontains='tina').first()

    default_categoria_id = str(tinas_categoria.id) if tinas_categoria else '1'

    # Obtener el ID de categoría del request o usar Tinas como default
    categoria_id = request.GET.get('categoria', default_categoria_id)

    try:
        fecha_seleccionada = datetime.strptime(fecha_str, '%Y-%m-%d').date()
    except ValueError:
        fecha_seleccionada = date.today()

    # Obtener la categoría seleccionada
    try:
        categoria = CategoriaServicio.objects.get(id=categoria_id)
    except CategoriaServicio.DoesNotExist:
        # Si no existe, intentar con Tinas Calientes
        categoria = tinas_categoria if tinas_categoria else categorias.first()
        categoria_id = categoria.id if categoria else None

    # Obtener servicios de la categoría que sean visibles en matriz
    servicios = Servicio.objects.filter(
        categoria=categoria,
        activo=True,
        visible_en_matriz=True  # Solo mostrar servicios marcados como visibles en matriz
    ).order_by('nombre')

    # Generar la matriz de disponibilidad
    matriz_data = generar_matriz_disponibilidad(
        fecha_seleccionada,
        categoria,
        servicios
    )

    # Crear una estructura de datos más simple para el template
    # Lista de listas para representar la matriz
    matriz_simple = []
    for slot in matriz_data['slots']:
        fila = {'slot': slot, 'celdas': []}
        for recurso in matriz_data['recursos']:
            if slot in matriz_data['matriz'] and recurso in matriz_data['matriz'][slot]:
                celda = matriz_data['matriz'][slot][recurso]
            else:
                celda = {'estado': 'disponible', 'cliente': None, 'personas': None}
            fila['celdas'].append(celda)
        matriz_simple.append(fila)


    # Contexto para el template
    context = {
        'fecha_seleccionada': fecha_seleccionada,
        'fecha_str': fecha_seleccionada.strftime('%Y-%m-%d'),
        'categoria_seleccionada': categoria,
        'categoria_id': int(categoria_id) if categoria_id else None,  # Convertir a int para comparación en template
        'categorias': categorias,
        'matriz': matriz_data['matriz'],
        'matriz_simple': matriz_simple,  # Nueva estructura para el template
        'slots_horarios': matriz_data['slots'],
        'recursos': matriz_data['recursos'],
        'resumen': matriz_data['resumen'],
    }

    # Usar template simple que funciona en producción
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

    # Obtener todas las reservas del día para esta categoría (solo de servicios visibles en matriz)
    reservas = ReservaServicio.objects.filter(
        fecha_agendamiento=fecha,
        servicio__categoria=categoria,
        servicio__visible_en_matriz=True,  # Solo considerar servicios visibles en matriz
        venta_reserva__estado_pago__in=['pagado', 'parcial', 'pendiente']
    ).select_related('servicio', 'venta_reserva', 'venta_reserva__cliente')

    # Usar los servicios visibles como recursos (columnas)
    recursos = [s.nombre for s in servicios]

    # Configurar slots según el tipo de categoría
    slots_por_servicio = {}  # Inicializar vacío por defecto

    if categoria and 'tina' in categoria.nombre.lower():
        # Definir los horarios específicos para tinas
        # Tinas SIN hidromasaje: Hornopiren, Tronador, Calbuco, Osorno
        slots_sin_hidromasaje = ["12:00", "14:30", "17:00", "19:30", "22:00"]
        # Tinas CON hidromasaje: Puntiagudo, Llaima, Villarrica, Puyehue
        slots_con_hidromasaje = ["14:00", "16:30", "19:00", "21:30"]

        # Crear diccionario de slots por servicio
        for servicio in servicios:
            nombre_lower = servicio.nombre.lower()
            # Verificar si es tina con hidromasaje
            if 'hidromasaje' in nombre_lower or 'puntiagudo' in nombre_lower or 'llaima' in nombre_lower or 'villarrica' in nombre_lower or 'puyehue' in nombre_lower:
                slots_por_servicio[servicio.nombre] = slots_con_hidromasaje
            else:
                # Es tina sin hidromasaje
                slots_por_servicio[servicio.nombre] = slots_sin_hidromasaje

        # Para la matriz, usar todos los slots posibles (para las filas)
        slots_set = set(slots_sin_hidromasaje + slots_con_hidromasaje)
        slots = sorted(list(slots_set))
    elif categoria and 'cabaña' in categoria.nombre.lower():
        # Para cabañas, solo mostrar el horario de check-in
        slots = ["16:00"]
    else:
        # Para otras categorías, intentar obtener slots de los servicios
        slots_set = set()
        for servicio in servicios:
            if servicio.slots_disponibles:
                for slot in servicio.slots_disponibles:
                    # Verificar que no sean días de la semana (bug de datos)
                    if slot.lower() not in ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                                           'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']:
                        slots_set.add(slot)

        if not slots_set:
            if categoria and 'masaje' in categoria.nombre.lower():
                # Para masajes, slots cada hora
                slots = generar_slots_horarios(
                    hora_inicio="09:00",
                    hora_fin="21:00",
                    duracion_minutos=60
                )
            else:
                # Para otros servicios
                slots = ["Check-in 15:00", "Check-out 12:00"]
        else:
            slots = sorted(list(slots_set))

    # Inicializar matriz
    matriz = {}
    for slot in slots:
        matriz[slot] = {}
        for recurso in recursos:
            # Para tinas, verificar si el slot corresponde a este recurso
            if categoria and 'tina' in categoria.nombre.lower() and 'slots_por_servicio' in locals():
                # Verificar si este slot es válido para este recurso
                if recurso in slots_por_servicio and slot in slots_por_servicio[recurso]:
                    estado = 'disponible'
                else:
                    estado = 'no_aplica'  # Este slot no existe para esta tina
            else:
                estado = 'disponible'

            matriz[slot][recurso] = {
                'estado': estado,
                'reserva': None,
                'cliente': None
            }

    # Marcar las reservas existentes en la matriz
    for reserva in reservas:
        hora_str = reserva.hora_inicio if reserva.hora_inicio else None

        # Buscar el slot correspondiente
        slot_encontrado = None
        if hora_str:
            # Normalizar el formato de hora (asegurar formato HH:MM)
            if ':' in hora_str:
                partes = hora_str.split(':')
                if len(partes) >= 2:
                    hora = int(partes[0])
                    minuto = int(partes[1])
                    hora_normalizada = f"{hora:02d}:{minuto:02d}"

                    # Buscar coincidencia exacta con la hora normalizada
                    if hora_normalizada in slots:
                        slot_encontrado = hora_normalizada

        if slot_encontrado and slot_encontrado in matriz:
            # Usar el nombre del servicio de la reserva como recurso
            recurso_nombre = reserva.servicio.nombre

            # Verificar si el recurso existe en la matriz
            if recurso_nombre in matriz[slot_encontrado]:
                matriz[slot_encontrado][recurso_nombre] = {
                    'estado': 'ocupado',
                    'reserva': reserva,
                    'cliente': reserva.venta_reserva.cliente.nombre if reserva.venta_reserva.cliente else 'Sin cliente',
                    'servicio': reserva.servicio.nombre,
                    'personas': reserva.cantidad_personas if reserva.cantidad_personas else 1,
                    'reserva_id': reserva.venta_reserva.id,
                    'estado_pago': reserva.venta_reserva.estado_pago
                }

    # Calcular resumen de ocupación (excluyendo slots que no aplican)
    slots_validos = sum(
        1 for slot in matriz.values()
        for recurso_data in slot.values()
        if recurso_data['estado'] != 'no_aplica'
    )
    ocupados = sum(
        1 for slot in matriz.values()
        for recurso_data in slot.values()
        if recurso_data['estado'] == 'ocupado'
    )

    resumen = {
        'total_slots': slots_validos,
        'ocupados': ocupados,
        'disponibles': slots_validos - ocupados,
        'porcentaje_ocupacion': round((ocupados / slots_validos * 100) if slots_validos > 0 else 0, 1)
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