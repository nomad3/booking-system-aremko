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

    # Crear estructura organizada por servicio (para vista mobile)
    servicios_con_horarios = []
    for recurso in matriz_data['recursos']:
        servicio_data = {
            'nombre': recurso,
            'slots': []
        }
        for slot in matriz_data['slots']:
            if slot in matriz_data['matriz'] and recurso in matriz_data['matriz'][slot]:
                slot_data = matriz_data['matriz'][slot][recurso].copy()
                slot_data['hora'] = slot
                servicio_data['slots'].append(slot_data)
            else:
                servicio_data['slots'].append({
                    'hora': slot,
                    'estado': 'disponible',
                    'cliente': None,
                    'personas': None
                })
        servicios_con_horarios.append(servicio_data)

    # Contexto para el template
    context = {
        'fecha_seleccionada': fecha_seleccionada,
        'fecha_str': fecha_seleccionada.strftime('%Y-%m-%d'),
        'categoria_seleccionada': categoria,
        'categoria_id': int(categoria_id) if categoria_id else None,  # Convertir a int para comparación en template
        'categorias': categorias,
        'matriz': matriz_data['matriz'],
        'matriz_simple': matriz_simple,  # Nueva estructura para el template
        'servicios_con_horarios': servicios_con_horarios,  # Para vista mobile
        'slots_horarios': matriz_data['slots'],
        'recursos': matriz_data['recursos'],
        'resumen': matriz_data['resumen'],
    }

    # Usar template simple que funciona en producción
    return render(request, 'ventas/calendario_matriz_simple.html', context)


def extraer_slots_para_fecha(slots_disponibles, fecha):
    """
    Extrae los slots disponibles para una fecha específica.

    Soporta dos formatos:
    1. Diccionario por día de semana: {"monday": ["12:00", "14:30"], "friday": ["12:00", "22:00"]}
    2. Lista simple: ["12:00", "14:30", "17:00"]

    Args:
        slots_disponibles: JSONField del servicio (puede ser dict o list)
        fecha: date object de la fecha seleccionada

    Returns:
        Lista de slots para ese día, o None si no hay configurados
    """
    if not slots_disponibles:
        return None

    # Si es un diccionario (formato por día de semana)
    if isinstance(slots_disponibles, dict):
        # Obtener el día de la semana en inglés (lowercase)
        # weekday() retorna 0=Monday, 1=Tuesday, ... 6=Sunday
        dias_semana = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        dia_nombre = dias_semana[fecha.weekday()]

        # Buscar slots para ese día
        slots_del_dia = slots_disponibles.get(dia_nombre, [])

        if slots_del_dia and len(slots_del_dia) > 0:
            return slots_del_dia
        else:
            return None

    # Si es una lista (formato simple - mismos horarios todos los días)
    elif isinstance(slots_disponibles, list):
        # Filtrar días de la semana que puedan estar en la lista por error
        slots_validos = [
            slot for slot in slots_disponibles
            if isinstance(slot, str) and slot.lower() not in [
                'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday',
                'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'
            ]
        ]
        if slots_validos:
            return slots_validos
        else:
            return None

    return None


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
    # NOTA: Se muestran TODAS las reservas independientemente del estado de pago
    # Los colores se asignan según el estado_pago en el template
    reservas = ReservaServicio.objects.filter(
        fecha_agendamiento=fecha,
        servicio__categoria=categoria,
        servicio__visible_en_matriz=True  # Solo considerar servicios visibles en matriz
    ).select_related('servicio', 'venta_reserva', 'venta_reserva__cliente')

    # Usar los servicios visibles como recursos (columnas)
    recursos = [s.nombre for s in servicios]

    # Configurar slots según el tipo de categoría
    slots_por_servicio = {}  # Diccionario de slots por servicio

    if categoria and 'tina' in categoria.nombre.lower():
        # HORARIOS DINÁMICOS: Usar slots_disponibles de cada servicio (soporta horarios por día)
        # Fallback a valores por defecto si no están configurados

        # Valores por defecto (fallback)
        # Tinas SIN hidromasaje: Hornopiren, Tronador, Calbuco, Osorno
        slots_sin_hidromasaje_default = ["12:00", "14:30", "17:00", "19:30", "22:00"]
        # Tinas CON hidromasaje: Puntiagudo, Llaima, Villarrica, Puyehue
        slots_con_hidromasaje_default = ["14:00", "16:30", "19:00", "21:30"]

        # Crear diccionario de slots por servicio
        slots_set = set()
        for servicio in servicios:
            # PRIORIDAD 1: Usar slots_disponibles configurados (soporta dict por día o list simple)
            slots_del_servicio = extraer_slots_para_fecha(servicio.slots_disponibles, fecha)

            if slots_del_servicio:
                slots_por_servicio[servicio.nombre] = slots_del_servicio
                slots_set.update(slots_del_servicio)
                continue

            # PRIORIDAD 2: Fallback a valores por defecto basados en el nombre
            nombre_lower = servicio.nombre.lower()
            if 'hidromasaje' in nombre_lower or 'puntiagudo' in nombre_lower or 'llaima' in nombre_lower or 'villarrica' in nombre_lower or 'puyehue' in nombre_lower:
                slots_por_servicio[servicio.nombre] = slots_con_hidromasaje_default
                slots_set.update(slots_con_hidromasaje_default)
            else:
                slots_por_servicio[servicio.nombre] = slots_sin_hidromasaje_default
                slots_set.update(slots_sin_hidromasaje_default)

        # Para la matriz, usar todos los slots recopilados
        slots = sorted(list(slots_set))

    elif categoria and 'cabaña' in categoria.nombre.lower():
        # HORARIOS DINÁMICOS para cabañas (soporta horarios por día)
        slots_set = set()
        for servicio in servicios:
            slots_del_servicio = extraer_slots_para_fecha(servicio.slots_disponibles, fecha)

            if slots_del_servicio:
                slots_por_servicio[servicio.nombre] = slots_del_servicio
                slots_set.update(slots_del_servicio)

        if slots_set:
            slots = sorted(list(slots_set))
        else:
            # Fallback: horario por defecto de check-in
            slots = ["16:00"]

    elif categoria and 'masaje' in categoria.nombre.lower():
        # HORARIOS DINÁMICOS para masajes (soporta horarios por día)
        slots_set = set()
        for servicio in servicios:
            slots_del_servicio = extraer_slots_para_fecha(servicio.slots_disponibles, fecha)

            if slots_del_servicio:
                slots_por_servicio[servicio.nombre] = slots_del_servicio
                slots_set.update(slots_del_servicio)

        if slots_set:
            slots = sorted(list(slots_set))
        else:
            # Fallback: horarios por defecto cada 1 hora 15 minutos
            slots = ["10:30", "11:45", "13:00", "14:15", "15:30", "16:45", "18:00", "19:15", "20:30", "21:45"]

    else:
        # Para otras categorías (soporta horarios por día)
        slots_set = set()
        for servicio in servicios:
            slots_del_servicio = extraer_slots_para_fecha(servicio.slots_disponibles, fecha)

            if slots_del_servicio:
                slots_por_servicio[servicio.nombre] = slots_del_servicio
                slots_set.update(slots_del_servicio)

        if not slots_set:
            # Para otros servicios por defecto
            slots = ["Check-in 15:00", "Check-out 12:00"]
        else:
            slots = sorted(list(slots_set))

    # Crear mapa de servicios para acceder a max_servicios_simultaneos
    servicios_map = {s.nombre: s for s in servicios}

    # Contar reservas por slot y servicio
    from collections import defaultdict
    contador_reservas = defaultdict(lambda: defaultdict(int))

    for reserva in reservas:
        hora_str = reserva.hora_inicio if reserva.hora_inicio else None
        if hora_str and ':' in hora_str:
            partes = hora_str.split(':')
            if len(partes) >= 2:
                hora = int(partes[0])
                minuto = int(partes[1])
                hora_normalizada = f"{hora:02d}:{minuto:02d}"
                recurso_nombre = reserva.servicio.nombre
                contador_reservas[hora_normalizada][recurso_nombre] += 1

    # Inicializar matriz
    matriz = {}
    for slot in slots:
        matriz[slot] = {}
        for recurso in recursos:
            # Obtener el servicio para acceder a max_servicios_simultaneos
            servicio = servicios_map.get(recurso)
            capacidad_max = servicio.max_servicios_simultaneos if servicio else 1
            reservas_count = contador_reservas[slot][recurso]

            # Para tinas, verificar si el slot corresponde a este recurso
            if categoria and 'tina' in categoria.nombre.lower() and 'slots_por_servicio' in locals():
                # Verificar si este slot es válido para este recurso
                if recurso in slots_por_servicio and slot in slots_por_servicio[recurso]:
                    # Verificar si aún hay capacidad disponible
                    if reservas_count < capacidad_max:
                        estado = 'disponible'
                    else:
                        estado = 'ocupado'
                else:
                    estado = 'no_aplica'  # Este slot no existe para esta tina
            else:
                # Verificar si aún hay capacidad disponible
                if reservas_count < capacidad_max:
                    estado = 'disponible'
                else:
                    estado = 'ocupado'

            matriz[slot][recurso] = {
                'estado': estado,
                'max_servicios_simultaneos': capacidad_max,
                'reservas_existentes': reservas_count,
                'servicio_nombre': recurso,
                'reserva': None,
                'cliente': None
            }

    # Marcar las reservas existentes en la matriz (para mostrar detalles)
    # Agrupar reservas por slot y servicio
    reservas_por_slot = defaultdict(lambda: defaultdict(list))
    for reserva in reservas:
        hora_str = reserva.hora_inicio if reserva.hora_inicio else None
        if hora_str and ':' in hora_str:
            partes = hora_str.split(':')
            if len(partes) >= 2:
                hora = int(partes[0])
                minuto = int(partes[1])
                hora_normalizada = f"{hora:02d}:{minuto:02d}"
                recurso_nombre = reserva.servicio.nombre
                reservas_por_slot[hora_normalizada][recurso_nombre].append(reserva)

    # Actualizar matriz con detalles de reservas
    for slot, servicios_reservas in reservas_por_slot.items():
        if slot in matriz:
            for recurso_nombre, lista_reservas in servicios_reservas.items():
                if recurso_nombre in matriz[slot]:
                    # Obtener info actual de la celda
                    celda_actual = matriz[slot][recurso_nombre]
                    capacidad_max = celda_actual.get('max_servicios_simultaneos', 1)
                    reservas_count = len(lista_reservas)

                    # Determinar estado real basado en capacidad
                    # Solo marcar como 'ocupado' si está COMPLETAMENTE lleno
                    if reservas_count >= capacidad_max:
                        nuevo_estado = 'ocupado'
                    else:
                        # Aún hay espacio, mantener como 'disponible'
                        nuevo_estado = celda_actual.get('estado', 'disponible')

                    # Agregar información de la primera reserva para mostrar
                    primera_reserva = lista_reservas[0] if lista_reservas else None
                    if primera_reserva:
                        matriz[slot][recurso_nombre].update({
                            'estado': nuevo_estado,
                            'reserva': primera_reserva,
                            'cliente': primera_reserva.venta_reserva.cliente.nombre if primera_reserva.venta_reserva.cliente else 'Sin cliente',
                            'personas': primera_reserva.cantidad_personas if primera_reserva.cantidad_personas else 1,
                            'reserva_id': primera_reserva.venta_reserva.id,
                            'estado_pago': primera_reserva.venta_reserva.estado_pago,
                            'servicio': primera_reserva.servicio.nombre,
                            'todas_reservas': lista_reservas  # Guardar todas las reservas para referencia
                        })

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