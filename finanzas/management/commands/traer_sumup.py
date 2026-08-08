# -*- coding: utf-8 -*-
"""P-22 F5: trae las comisiones de SumUp por API (payouts con su fee).

El cron ya lo hace cada hora vía auditoria_horaria (ventana 7 días); este
comando existe para el BACKFILL manual desde julio:

    python manage.py traer_sumup --dias 40
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Registra las comisiones SumUp como gasto (idempotente).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7)

    def handle(self, *args, **opts):
        from finanzas.services import traer_comisiones_sumup

        creados, total = traer_comisiones_sumup(dias=opts['dias'])
        self.stdout.write(self.style.SUCCESS(
            f'SumUp: {total} payouts revisados en {opts["dias"]} días · '
            f'{creados} comisiones nuevas registradas'))
