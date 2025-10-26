import traceback
from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from ..models import Servicio, ReservaServicio # Relative imports

# Helper function to check slot availability (used internally or by other views)
def is_slot_available(servicio, fecha, hora):
    """Checks if a specific service slot (date and time) is available."""
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
        reservas = ReservaServicio.objects.filter(
            servicio=servicio,
            fecha_agendamiento=fecha_obj
        ).values_list('hora_inicio', flat=True)
        # Ensure booked slots are strings for comparison, handle potential None values from DB
        booked_slots = set(str(h) for h in reservas if h is not None)
        print(f"[get_available_hours] Booked slots for {fecha_obj}: {booked_slots}") # Debug booked slots

        # --- Filter available slots by removing booked ones ---
        # Ensure slots from config are also strings for comparison
        horas_disponibles = [str(hora) for hora in available_slots_for_day if str(hora) not in booked_slots]
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
