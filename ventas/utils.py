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

def verificar_disponibilidad(servicio, fecha_inicio, fecha_fin):
    """
    Verifica si el servicio está disponible en el rango de fechas especificado.
    """
    reservas = ReservaServicio.objects.filter(
        Q(servicio=servicio) & 
        (Q(fecha_agendamiento__lte=fecha_fin) & Q(fecha_agendamiento__gte=fecha_inicio))
    )
    return not reservas.exists()
