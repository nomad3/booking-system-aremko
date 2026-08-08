# -*- coding: utf-8 -*-
"""P-22: la auditoría horaria completa, en un solo comando para el cron de Render
(«revisar pagos», cada hora):

    python manage.py auditoria_horaria

1. Pagos de Mercado Pago por API (cobros → cola de Deborah, compras → gasto).
2. Correos de transferencias salientes MP (pagos a trabajadores, barridos).

Cada paso va aislado: si uno falla, el otro corre igual. El comando termina con
error solo si TODOS los pasos fallaron (para que Render marque la corrida roja).
"""
import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Corre la auditoría completa: pagos MP por API + correos de plata.'

    def handle(self, *args, **opts):
        fallos = []

        try:
            call_command('traer_pagos_mp', dias=3)
        except Exception as e:
            logger.exception('auditoria_horaria: traer_pagos_mp falló')
            self.stderr.write(self.style.ERROR(f'traer_pagos_mp falló: {e}'))
            fallos.append('traer_pagos_mp')

        try:
            call_command('ingerir_correos_finanzas', dias=7, aplicar=True)
        except Exception as e:
            logger.exception('auditoria_horaria: ingerir_correos_finanzas falló')
            self.stderr.write(self.style.ERROR(f'ingerir_correos_finanzas falló: {e}'))
            fallos.append('ingerir_correos_finanzas')

        if len(fallos) == 2:
            raise CommandError(f'Todos los pasos fallaron: {fallos}')
        if fallos:
            self.stdout.write(self.style.WARNING(
                f'Terminó con un paso caído: {fallos[0]} (el resto corrió).'))
        else:
            self.stdout.write(self.style.SUCCESS('Auditoría horaria completa.'))
