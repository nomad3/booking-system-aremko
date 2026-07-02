# -*- coding: utf-8 -*-
"""Muestra SOLO el client_email de la cuenta de servicio de Google (GA4/GSC).

No es un secreto (es un identificador tipo "...@proyecto.iam.gserviceaccount.com",
no la clave privada) — sirve para agregarla como usuario en Google Search Console
(Configuración → Usuarios y permisos → Agregar usuario), ya que GA4 y GSC comparten
la misma cuenta de servicio pero los permisos se otorgan por separado en cada
producto de Google (H-057: confirmado 403 "User does not have sufficient
permission for site" en GSC, mientras GA4 funciona bien con la misma cuenta).

NUNCA imprime private_key, private_key_id ni el resto del JSON.

Uso:
    python manage.py mostrar_service_account_email
"""
import json

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Muestra el client_email de la cuenta de servicio de Google (para darla de alta en GSC)."

    def handle(self, *args, **opts):
        raw_json = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_JSON', '') or ''
        file_path = getattr(settings, 'GOOGLE_SERVICE_ACCOUNT_FILE', '') or ''

        info = None
        if raw_json.strip():
            info = json.loads(raw_json)
        elif file_path:
            with open(file_path) as f:
                info = json.load(f)
        else:
            self.stdout.write(self.style.ERROR(
                'No hay GOOGLE_SERVICE_ACCOUNT_JSON ni GOOGLE_SERVICE_ACCOUNT_FILE configurados.'
            ))
            return

        email = info.get('client_email', '(no encontrado en el JSON)')
        project_id = info.get('project_id', '(no encontrado)')

        self.stdout.write(self.style.SUCCESS(f'client_email: {email}'))
        self.stdout.write(f'project_id: {project_id}')
        self.stdout.write(
            '\nSiguiente paso: entrar a https://search.google.com/search-console/users '
            "(propiedad aremko.cl) → Agregar usuario → pegar el client_email de arriba → "
            'permiso "Completo" o "Restringido" (con Restringido alcanza para leer).'
        )
