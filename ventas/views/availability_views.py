import traceback
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ..models import Servicio, ReservaServicio, ServicioBloqueo # Relative imports

# Helper function to check slot availability (used internally or by other views)
def is_slot_available(servicio, fecha, hora):
    """Checks if a specific service slot (date and time) is available."""
    from ventas.models import ServicioSlotBloqueo

    # CRITICAL 1: Check if the service is blocked by DAY (día completo)
    if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio.id, fecha):
        return False

    # CRITICAL 2: Check if the specific SLOT is blocked (bloqueo de slot individual)
    if ServicioSlotBloqueo.slot_bloqueado(servicio.id, fecha, hora):
        return False

    # Check if there are any existing reservations for this service, date and time
    existing_reservas = ReservaServicio.objects.filter(
        servicio=servicio,
        fecha_agendamiento=fecha,
        hora_inicio=hora
    )
    # If there are no existing reservations, the slot is available
    return not existing_reservas.exists()

def get_available_hours(request):
    """
    API endpoint to get available hours for a service on a specific date.
    """
    servicio_id = request.GET.get('servicio_id')
    fecha_str = request.GET.get('fecha')

    if not servicio_id or not fecha_str:
        return JsonResponse({'success': False, 'error': 'Faltan parámetros servicio_id o fecha.'}, status=400)

    try:
        servicio = get_object_or_404(Servicio, id=servicio_id)
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()
        print(f"[get_available_hours] Date requested: {fecha_obj}") # Debug date

        # CRITICAL: Check if service is blocked on this date
        if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, fecha_obj):
            print(f"[get_available_hours] Service {servicio_id} is BLOCKED on {fecha_obj}")
            return JsonResponse({'success': True, 'horas_disponibles': [], 'bloqueado': True})

        day_name = fecha_obj.strftime('%A').lower() # Get day name in English lowercase (e.g., 'monday')
        print(f"[get_available_hours] Day name calculated: {day_name}") # Debug day name

        # --- Get slots for the specific day from the JSON field ---
        print(f"[get_available_hours] Raw slots_disponibles from DB for service {servicio.id}: {servicio.slots_disponibles}") # Debug raw data
        print(f"[get_available_hours] Type of slots_disponibles: {type(servicio.slots_disponibles)}") # Debug type
        # Ensure slots_disponibles is a dict
        daily_slots_config = servicio.slots_disponibles if isinstance(servicio.slots_disponibles, dict) else {}
        print(f"[get_available_hours] Interpreted daily_slots_config: {daily_slots_config}") # Debug interpreted dict
        available_slots_for_day = daily_slots_config.get(day_name, []) # Get slots for the specific day, default to empty list
        print(f"[get_available_hours] Slots found for {day_name}: {available_slots_for_day}") # Debug slots for the day

        if not available_slots_for_day:
             # If no specific slots defined for the day, return empty.
             print(f"[get_available_hours] No slots defined in JSON for service {servicio_id} on {day_name}")
             return JsonResponse({'success': True, 'horas_disponibles': []})

        # --- Get existing reservations for this service on this date ---
        from django.db.models import Count
        reservas_por_hora = ReservaServicio.objects.filter(
            servicio=servicio,
            fecha_agendamiento=fecha_obj
        ).values('hora_inicio').annotate(cantidad=Count('id'))

        # Crear diccionario de slots ocupados con su cantidad
        slots_ocupacion = {str(r['hora_inicio']): r['cantidad'] for r in reservas_por_hora}
        print(f"[get_available_hours] Slots ocupation for {fecha_obj}: {slots_ocupacion}") # Debug slots occupation

        # Obtener capacidad de servicios simultáneos del servicio
        max_simultaneos = getattr(servicio, 'max_servicios_simultaneos', 1)
        print(f"[get_available_hours] Servicio {servicio.nombre} max_servicios_simultaneos: {max_simultaneos}") # Debug capacity

        # --- Get blocked slots (bloqueos de slot individuales) ---
        from ventas.models import ServicioSlotBloqueo
        bloqueos_slot = ServicioSlotBloqueo.objects.filter(
            servicio=servicio,
            fecha=fecha_obj,
            activo=True
        ).values_list('hora_slot', flat=True)
        slots_bloqueados_set = set(bloqueos_slot)
        print(f"[get_available_hours] Blocked slots: {slots_bloqueados_set}") # Debug blocked slots

        # --- Filter available slots considering capacity AND slot blocks ---
        # Un slot está disponible si:
        # 1. Tiene menos reservas que el máximo de servicios simultáneos
        # 2. NO está bloqueado individualmente
        horas_disponibles = []
        for hora in available_slots_for_day:
            hora_str = str(hora)

            # Verificar si está bloqueado
            if hora_str in slots_bloqueados_set:
                print(f"[get_available_hours] Slot {hora_str} is BLOCKED - skipping")
                continue

            # Verificar capacidad
            reservas_existentes = slots_ocupacion.get(hora_str, 0)
            if reservas_existentes < max_simultaneos:
                horas_disponibles.append(hora_str)

        print(f"[get_available_hours] Filtered available hours: {horas_disponibles}") # Debug filtered list

        # --- Sort the final list ---
        # Sort based on time (assuming HH:MM format)
        try:
            horas_disponibles.sort(key=lambda x: datetime.strptime(x, '%H:%M').time())
        except ValueError:
            horas_disponibles.sort() # Fallback to string sort if format is unexpected
        print(f"[get_available_hours] Final sorted list: {horas_disponibles}") # Debug final list

        return JsonResponse({'success': True, 'horas_disponibles': horas_disponibles})

    except Servicio.DoesNotExist:
         # This case is handled by get_object_or_404, but kept for clarity
        return JsonResponse({'success': False, 'error': 'Servicio no encontrado'}, status=404)
    except ValueError as e:
        # Handle potential date parsing errors
        print(f"Error parsing date in get_available_hours: {e}")
        return JsonResponse({'success': False, 'error': f'Error de formato de fecha: {str(e)}'}, status=400)
    except Exception as e:
        print(f"Error en get_available_hours: {str(e)}")
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)

def check_slot_availability(request):
    """
    API endpoint to check if a specific service slot (date and time) is available.
    """
    servicio_id = request.GET.get('servicio_id')
    fecha_str = request.GET.get('fecha')
    hora = request.GET.get('hora')

    if not all([servicio_id, fecha_str, hora]):
        return JsonResponse({'available': False, 'error': 'Missing parameters'}, status=400)

    try:
        servicio = get_object_or_404(Servicio, id=servicio_id)
        fecha = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # Use the helper function
        slot_is_available = is_slot_available(servicio, fecha, hora)

        return JsonResponse({'available': slot_is_available})

    # Note: Servicio.DoesNotExist is handled by get_object_or_404 raising Http404
    except ValueError:
        return JsonResponse({'available': False, 'error': 'Formato de fecha inválido'}, status=400)
    except Exception as e:
        # Log the exception for debugging
        print(f"Error checking slot availability: {e}")
        traceback.print_exc()
        return JsonResponse({'available': False, 'error': 'Error interno del servidor'}, status=500)

def get_slots_disponibles_para_bloquear(request):
    """
    API endpoint para obtener slots disponibles para bloquear.

    Retorna solo los slots que:
    - NO tienen reservas
    - NO están bloqueados por día completo
    - NO están bloqueados por slot individual

    Usado por el admin de ServicioSlotBloqueo para mostrar solo slots bloqueables.
    """
    servicio_id = request.GET.get('servicio_id')
    fecha_str = request.GET.get('fecha')

    if not servicio_id or not fecha_str:
        return JsonResponse({'success': False, 'error': 'Faltan parámetros'}, status=400)

    try:
        servicio = get_object_or_404(Servicio, id=servicio_id)
        fecha_obj = datetime.strptime(fecha_str, '%Y-%m-%d').date()

        # 1. Verificar si el día está bloqueado completamente
        if ServicioBloqueo.servicio_bloqueado_en_fecha(servicio_id, fecha_obj):
            return JsonResponse({
                'success': True,
                'slots_disponibles': [],
                'mensaje': 'Este servicio está bloqueado por día completo en esta fecha'
            })

        # 2. Obtener slots configurados para este servicio en esta fecha
        from ventas.views.calendario_matriz_view import extraer_slots_para_fecha
        slots_configurados = extraer_slots_para_fecha(servicio.slots_disponibles, fecha_obj)

        if not slots_configurados:
            return JsonResponse({
                'success': True,
                'slots_disponibles': [],
                'mensaje': 'Este servicio no tiene horarios configurados para este día'
            })

        # 3. Obtener reservas existentes
        from django.db.models import Count
        reservas_por_hora = ReservaServicio.objects.filter(
            servicio=servicio,
            fecha_agendamiento=fecha_obj
        ).exclude(
            venta_reserva__estado_reserva='cancelada'
        ).values('hora_inicio').annotate(cantidad=Count('id'))

        slots_ocupados = {r['hora_inicio']: r['cantidad'] for r in reservas_por_hora}

        # 4. Obtener bloqueos de slot existentes
        from ventas.models import ServicioSlotBloqueo
        bloqueos_slot = ServicioSlotBloqueo.objects.filter(
            servicio=servicio,
            fecha=fecha_obj,
            activo=True
        ).values_list('hora_slot', flat=True)

        slots_bloqueados_set = set(bloqueos_slot)

        # 5. Filtrar slots disponibles
        max_simultaneos = getattr(servicio, 'max_servicios_simultaneos', 1)
        slots_disponibles = []

        for hora in slots_configurados:
            hora_str = str(hora)

            # Verificar si está bloqueado individualmente
            if hora_str in slots_bloqueados_set:
                continue

            # Verificar si tiene capacidad disponible
            reservas_existentes = slots_ocupados.get(hora_str, 0)
            if reservas_existentes < max_simultaneos:
                slots_disponibles.append(hora_str)

        return JsonResponse({
            'success': True,
            'slots_disponibles': sorted(slots_disponibles)
        })

    except Servicio.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Servicio no encontrado'}, status=404)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': f'Error de formato: {str(e)}'}, status=400)
    except Exception as e:
        print(f"Error en get_slots_disponibles_para_bloquear: {str(e)}")
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': f'Error interno: {str(e)}'}, status=500)
