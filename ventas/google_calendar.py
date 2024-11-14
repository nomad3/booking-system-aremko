from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

SCOPES = ['https://www.googleapis.com/auth/calendar']

def get_google_calendar_service():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    return service

def create_google_calendar_event(reserva):
    service = get_google_calendar_service()
    event = {
        'summary': f'Reserva de {reserva.cliente.nombre}',
        'start': {'dateTime': reserva.fecha_inicio.isoformat(), 'timeZone': 'America/Santiago'},
        'end': {'dateTime': reserva.fecha_fin.isoformat(), 'timeZone': 'America/Santiago'},
    }
    service.events().insert(calendarId='primary', body=event).execute()
