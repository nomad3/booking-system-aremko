# -*- coding: utf-8 -*-
"""Espeja los calendarios de Booking/Airbnb como bloqueos (H-106 Fase 2).

Pensado para correr cada 15 minutos como Cron Job de Render:

    python manage.py sincronizar_calendarios_ota

Primera vez en la Shell, sin escribir nada:

    python manage.py sincronizar_calendarios_ota --dry-run

La lógica vive en `ventas/ota_sync.py` (reglas: espejar-no-acumular, lectura
fallida no toca nada, lo importado no se reexporta).
"""
from django.core.management.base import BaseCommand

from ventas.ota_sync import sincronizar_todo


class Command(BaseCommand):
    help = 'Lee los iCal de Booking/Airbnb y espeja bloqueos [OTA] por cabaña.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run', action='store_true',
            help='Lee y muestra qué haría, sin escribir bloqueos.')

    def handle(self, *args, **opts):
        informes = sincronizar_todo(dry_run=opts['dry_run'])
        if not informes:
            self.stdout.write('Sin calendarios activos con URL de OTA que leer.')
            return
        hubo_overbooking = False
        for linea in informes:
            if 'OVERBOOKING' in linea:
                hubo_overbooking = True
                self.stdout.write(self.style.ERROR(linea))
            elif 'SIN CAMBIOS' in linea:
                self.stdout.write(self.style.WARNING(linea))
            else:
                self.stdout.write(self.style.SUCCESS(linea))
        if hubo_overbooking:
            self.stdout.write(self.style.ERROR(
                '⚠️ Hay overbooking: la misma noche está vendida en Aremko y '
                'en la OTA. Resolver a mano con el cliente ANTES de que llegue.'))
