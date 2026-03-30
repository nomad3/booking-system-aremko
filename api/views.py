"""
API Views for Aremko Spa Availability
"""

from datetime import datetime, timedelta
from rest_framework import status
from rest_framework.decorators import api_view, authentication_classes
from rest_framework.response import Response
from django.db.models import Q, Count
from django.shortcuts import get_object_or_404

from .authentication import APIKeyAuthentication
from .serializers import (
    TubAvailabilityResponseSerializer,
    MassageAvailabilityResponseSerializer,
    CabinAvailabilityResponseSerializer,
    AvailabilitySummaryResponseSerializer,
)
from ventas.models import (
    Servicio, ReservaServicio, VentaReserva,
    ServicioBloqueo, ServicioSlotBloqueo,
    CategoriaServicio, Producto
)


def get_available_slots_for_service(servicio, fecha):
    """
    Helper function to get available slots for a service on a specific date.
    Reuses logic from existing availability system.
    """
    # Check if service is blocked for this entire date
    if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio.id, fecha):
        return []

    # Get day name for slot configuration
    day_name = fecha.strftime('%A').lower()

    # Get configured slots for this day
    daily_slots_config = servicio.slots_disponibles if isinstance(servicio.slots_disponibles, dict) else {}
    available_slots_for_day = daily_slots_config.get(day_name, [])

    if not available_slots_for_day:
        return []

    # Get existing reservations count per slot
    reservas_por_hora = ReservaServicio.objects.filter(
        servicio=servicio,
        fecha_agendamiento=fecha
    ).values('hora_inicio').annotate(cantidad=Count('id'))

    slots_ocupacion = {str(r['hora_inicio']): r['cantidad'] for r in reservas_por_hora}

    # Get max simultaneous services
    max_simultaneos = getattr(servicio, 'max_servicios_simultaneos', 1)

    # Get blocked slots
    bloqueos_slot = ServicioSlotBloqueo.objects.filter(
        servicio=servicio,
        fecha=fecha,
        activo=True
    ).values_list('hora_slot', flat=True)
    slots_bloqueados_set = set(bloqueos_slot)

    # Filter available slots
    horas_disponibles = []
    for hora in available_slots_for_day:
        hora_str = str(hora)

        # Skip if blocked
        if hora_str in slots_bloqueados_set:
            continue

        # Check capacity
        reservas_count = slots_ocupacion.get(hora_str, 0)
        if reservas_count < max_simultaneos:
            horas_disponibles.append(hora_str)

    return horas_disponibles


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def tinajas_availability(request):
    """
    GET /api/v1/availability/tinajas/
    Query params: date (YYYY-MM-DD), persons (int, optional)
    """
    date_str = request.GET.get('date')
    persons = request.GET.get('persons', 1)

    if not date_str:
        return Response(
            {'error': 'Date parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        fecha = datetime.strptime(date_str, '%Y-%m-%d').date()
        persons = int(persons)
    except (ValueError, TypeError):
        return Response(
            {'error': 'Invalid date format or persons value'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get hot tub services (Tinajas category)
    try:
        categoria_tinajas = CategoriaServicio.objects.get(
            Q(nombre__icontains='tinaja') | Q(nombre__icontains='tina')
        )
    except CategoriaServicio.DoesNotExist:
        return Response(
            {'error': 'Hot tubs category not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Get all active hot tub services
    tinajas = Servicio.objects.filter(
        categoria=categoria_tinajas,
        activo=True,
        publicado_web=True
    )

    available_slots = []
    for tina in tinajas:
        slots = get_available_slots_for_service(tina, fecha)
        if slots:
            # Map tub names to their common names
            tub_name = tina.nombre.replace('Tinaja ', '').replace('Tina ', '')

            available_slots.append({
                'tub_name': tub_name,
                'tub_id': tina.id,
                'slots': slots,
                'price_per_person': int(tina.precio_base),
                'duration_minutes': tina.duracion
            })

    response_data = {
        'date': fecha,
        'service': 'tinajas',
        'available_slots': available_slots
    }

    serializer = TubAvailabilityResponseSerializer(data=response_data)
    if serializer.is_valid():
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def masajes_availability(request):
    """
    GET /api/v1/availability/masajes/
    Query params: date (YYYY-MM-DD), type (optional)
    """
    date_str = request.GET.get('date')
    massage_type = request.GET.get('type')

    if not date_str:
        return Response(
            {'error': 'Date parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        fecha = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Get massage services
    try:
        categoria_masajes = CategoriaServicio.objects.get(
            nombre__icontains='masaje'
        )
    except CategoriaServicio.DoesNotExist:
        return Response(
            {'error': 'Massage category not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Filter by type if provided
    masajes_query = Servicio.objects.filter(
        categoria=categoria_masajes,
        activo=True,
        publicado_web=True
    )

    if massage_type:
        type_mapping = {
            'relajacion': 'relajaci',
            'deportivo': 'deportiv',
            'piedras': 'piedra',
            'thai': 'thai',
            'drenaje': 'drenaje',
            'reflexologia': 'reflexo'
        }
        search_term = type_mapping.get(massage_type, massage_type)
        masajes_query = masajes_query.filter(nombre__icontains=search_term)

    available_slots = []
    for masaje in masajes_query:
        slots = get_available_slots_for_service(masaje, fecha)
        if slots:
            # Extract massage type from name
            massage_name = masaje.nombre.lower()
            if 'relajaci' in massage_name:
                type_name = 'relajacion'
            elif 'deportiv' in massage_name:
                type_name = 'deportivo'
            elif 'piedra' in massage_name:
                type_name = 'piedras'
            elif 'thai' in massage_name:
                type_name = 'thai'
            elif 'drenaje' in massage_name:
                type_name = 'drenaje'
            elif 'reflexo' in massage_name:
                type_name = 'reflexologia'
            else:
                type_name = 'otro'

            available_slots.append({
                'type': type_name,
                'type_id': masaje.id,
                'slots': slots,
                'price': int(masaje.precio_base),
                'duration_minutes': masaje.duracion
            })

    response_data = {
        'date': fecha,
        'service': 'masajes',
        'available_slots': available_slots
    }

    serializer = MassageAvailabilityResponseSerializer(data=response_data)
    if serializer.is_valid():
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def cabanas_availability(request):
    """
    GET /api/v1/availability/cabanas/
    Query params: checkin (YYYY-MM-DD), checkout (YYYY-MM-DD), persons (optional)
    """
    checkin_str = request.GET.get('checkin')
    checkout_str = request.GET.get('checkout')
    persons = request.GET.get('persons', 2)

    if not checkin_str or not checkout_str:
        return Response(
            {'error': 'Checkin and checkout dates are required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        checkin = datetime.strptime(checkin_str, '%Y-%m-%d').date()
        checkout = datetime.strptime(checkout_str, '%Y-%m-%d').date()
        persons = int(persons)
    except (ValueError, TypeError):
        return Response(
            {'error': 'Invalid date format or persons value'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if checkout <= checkin:
        return Response(
            {'error': 'Checkout must be after checkin'},
            status=status.HTTP_400_BAD_REQUEST
        )

    nights = (checkout - checkin).days

    # Get cabin services
    try:
        categoria_cabanas = CategoriaServicio.objects.get(
            Q(nombre__icontains='cabaña') | Q(nombre__icontains='cabana')
        )
    except CategoriaServicio.DoesNotExist:
        return Response(
            {'error': 'Cabins category not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    cabanas = Servicio.objects.filter(
        categoria=categoria_cabanas,
        activo=True,
        publicado_web=True,
        capacidad_maxima__gte=persons
    )

    available_cabins = []
    for cabana in cabanas:
        # Check availability for all dates in the range
        is_available = True
        current_date = checkin

        while current_date < checkout:
            # Check if cabin is blocked on any date
            if ServicioBloqueo.servicio_bloqueado_en_fecha(cabana.id, current_date):
                is_available = False
                break

            # Check for existing reservations
            existing = ReservaServicio.objects.filter(
                servicio=cabana,
                fecha_agendamiento=current_date
            ).exists()

            if existing:
                is_available = False
                break

            current_date += timedelta(days=1)

        if is_available:
            # Get available add-ons
            addons = [
                {'name': 'Desayuno', 'price': 20000},
                {'name': 'Tinaja privada', 'price': 25000},
                {'name': 'Masaje', 'price': 40000}
            ]

            available_cabins.append({
                'cabin_id': cabana.id,
                'cabin_name': cabana.nombre,
                'max_persons': cabana.capacidad_maxima,
                'price_per_night': int(cabana.precio_base),
                'nights': nights,
                'total_price': int(cabana.precio_base) * nights,
                'addons_available': addons
            })

    response_data = {
        'checkin': checkin,
        'checkout': checkout,
        'service': 'cabanas',
        'available_cabins': available_cabins
    }

    serializer = CabinAvailabilityResponseSerializer(data=response_data)
    if serializer.is_valid():
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@authentication_classes([APIKeyAuthentication])
def availability_summary(request):
    """
    GET /api/v1/availability/summary/
    Query params: date (YYYY-MM-DD)
    """
    date_str = request.GET.get('date')

    if not date_str:
        return Response(
            {'error': 'Date parameter is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        fecha = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return Response(
            {'error': 'Invalid date format'},
            status=status.HTTP_400_BAD_REQUEST
        )

    summary = {}

    # Check tinajas availability
    try:
        categoria_tinajas = CategoriaServicio.objects.get(
            Q(nombre__icontains='tinaja') | Q(nombre__icontains='tina')
        )
        tinajas = Servicio.objects.filter(
            categoria=categoria_tinajas,
            activo=True,
            publicado_web=True
        )

        total_tub_slots = 0
        for tina in tinajas:
            slots = get_available_slots_for_service(tina, fecha)
            total_tub_slots += len(slots)

        summary['tinajas'] = {
            'available': total_tub_slots > 0,
            'slots_count': total_tub_slots
        }
    except CategoriaServicio.DoesNotExist:
        summary['tinajas'] = {
            'available': False,
            'slots_count': 0
        }

    # Check masajes availability
    try:
        categoria_masajes = CategoriaServicio.objects.get(
            nombre__icontains='masaje'
        )
        masajes = Servicio.objects.filter(
            categoria=categoria_masajes,
            activo=True,
            publicado_web=True
        )

        total_massage_slots = 0
        for masaje in masajes:
            slots = get_available_slots_for_service(masaje, fecha)
            total_massage_slots += len(slots)

        summary['masajes'] = {
            'available': total_massage_slots > 0,
            'slots_count': total_massage_slots
        }
    except CategoriaServicio.DoesNotExist:
        summary['masajes'] = {
            'available': False,
            'slots_count': 0
        }

    # Check cabanas availability
    try:
        categoria_cabanas = CategoriaServicio.objects.get(
            Q(nombre__icontains='cabaña') | Q(nombre__icontains='cabana')
        )
        cabanas = Servicio.objects.filter(
            categoria=categoria_cabanas,
            activo=True,
            publicado_web=True
        )

        available_cabins = 0
        for cabana in cabanas:
            # Check if cabin is available on this date
            if not ServicioBloqueo.servicio_bloqueado_en_fecha(cabana.id, fecha):
                existing = ReservaServicio.objects.filter(
                    servicio=cabana,
                    fecha_agendamiento=fecha
                ).exists()
                if not existing:
                    available_cabins += 1

        summary['cabanas'] = {
            'available': available_cabins > 0,
            'cabins_count': available_cabins
        }
    except CategoriaServicio.DoesNotExist:
        summary['cabanas'] = {
            'available': False,
            'cabins_count': 0
        }

    response_data = {
        'date': fecha,
        'summary': summary
    }

    return Response(response_data)