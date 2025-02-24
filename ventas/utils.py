from googleapiclient.discovery import build
from google.oauth2 import service_account
from datetime import timedelta
from django.conf import settings
from django.db.models import Q
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

def verificar_disponibilidad(servicio, fecha_propuesta, hora_propuesta, cantidad_personas=1):
    """
    Nueva lógica que verifica:
    1. Si el slot horario está dentro de los slots disponibles del servicio
    2. Si hay capacidad suficiente en el slot seleccionado
    """
    try:
        # 1. Verificar si el slot está disponible en el servicio
        if hora_propuesta not in servicio.slots_disponibles:
            return False

        # 2. Calcular capacidad ocupada en el mismo slot
        reservas_existentes = ReservaServicio.objects.filter(
            servicio=servicio,
            fecha_agendamiento=fecha_propuesta,
            hora_inicio=hora_propuesta
        )

        capacidad_ocupada = sum(reserva.cantidad_personas for reserva in reservas_existentes)
        
        # 3. Verificar capacidad máxima
        return (capacidad_ocupada + cantidad_personas) <= servicio.capacidad_maxima

    except Exception as e:
        print(f"Error en verificación de disponibilidad: {e}")
        return False
