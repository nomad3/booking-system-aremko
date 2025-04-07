from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import timedelta
from django.conf import settings
from django.db.models import Q, Sum # Import Sum
from .models import ReservaServicio
import os

def crear_evento_calendar(reserva):
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    SERVICE_ACCOUNT_FILE = os.path.join(settings.BASE_DIR, 'credenciales.json')

    credentials = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE, scopes=SCOPES)

    service = build('calendar', 'v3', credentials=credentials)

    evento = {
        'summary': f"Reserva de {reserva.producto.nombre}",
        'description': f"Cliente: {reserva.cliente}",
        'start': {
            'dateTime': reserva.fecha_reserva.isoformat(),
            'timeZone': settings.TIME_ZONE,
        },
        'end': {
            'dateTime': (reserva.fecha_reserva + reserva.producto.duracion_reserva).isoformat(),
            'timeZone': settings.TIME_ZONE,
        },
    }

    # Argumento posicional primero, luego el de palabra clave
    evento_creado = service.events().insert('tu_calendar_id', body=evento).execute()
    return evento_creado.get('id')

def verificar_disponibilidad(servicio, fecha_propuesta, hora_propuesta, cantidad_personas=1, reserva_actual=None):
    """
    Verifica la disponibilidad de un slot para un servicio.

    Args:
        servicio: Instancia del modelo Servicio.
        fecha_propuesta: Objeto date para la fecha deseada.
        hora_propuesta: String 'HH:MM' para la hora deseada.
        cantidad_personas: Número de personas para la reserva.
        reserva_actual: Instancia opcional de ReservaServicio (para excluirla al editar).

    Returns:
        True si el slot está disponible, False en caso contrario.
    """
    try:
        # 1. Verificar si el slot está definido para el día de la semana
        day_name = fecha_propuesta.strftime('%A').lower()
        slots_config = servicio.slots_disponibles if isinstance(servicio.slots_disponibles, dict) else {}
        slots_for_day = slots_config.get(day_name, [])
        if hora_propuesta not in slots_for_day:
            print(f"DEBUG: Slot {hora_propuesta} no definido en {slots_for_day} para {day_name}")
            return False # Slot no definido para este día

        # 2. Calcular capacidad ocupada en el mismo slot, excluyendo la reserva actual si se está editando
        query = ReservaServicio.objects.filter(
            servicio=servicio,
            fecha_agendamiento=fecha_propuesta,
            hora_inicio=hora_propuesta
        )
        # Si estamos validando una instancia existente (al editar), la excluimos de la cuenta
        if reserva_actual and reserva_actual.pk:
            query = query.exclude(pk=reserva_actual.pk)

        capacidad_ocupada = query.aggregate(total_personas=Sum('cantidad_personas'))['total_personas'] or 0

        # 3. Verificar si la nueva reserva excede la capacidad máxima
        capacidad_maxima = servicio.capacidad_maxima if hasattr(servicio, 'capacidad_maxima') else 1
        return (capacidad_ocupada + cantidad_personas) <= capacidad_maxima

    except Exception as e:
        print(f"Error en verificación de disponibilidad: {e}")
        return False
