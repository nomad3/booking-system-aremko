# -*- coding: utf-8 -*-
"""Cron P-22 F2-C: mantiene frescos los datos de Mercado Pago sin depender del
botón de Deborah. Un solo fetch alimenta a los dos consumidores:

- cobros nuevos → MovimientoMP (cola de conciliación de Deborah, con sugerencia)
- compras donde Aremko es el pagador → gasto automático en finanzas (F2-B)

Pensado para un Cron Job de Render cada hora (mismo patrón que aremko-reminders):

    python manage.py traer_pagos_mp --dias 3

La ventana de 3 días re-mira los últimos días A PROPÓSITO: si una corrida falla,
la siguiente recoge lo perdido — todo el circuito es idempotente (cobros por
mp_payment_id, gastos por referencia mp:<id>).
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Trae pagos de Mercado Pago: cobros → conciliación, compras → finanzas.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=3,
                            help='Días hacia atrás a revisar (default 3).')

    def handle(self, *args, **opts):
        from conciliacion.services_mp import traer_pagos_mp

        nuevos, total = traer_pagos_mp(dias=opts['dias'])
        self.stdout.write(self.style.SUCCESS(
            f'MP: {total} pagos revisados en {opts["dias"]} días · '
            f'{len(nuevos)} cobros nuevos en la cola'))
        for m in nuevos:
            linea = (f'  {m.fecha:%d-%m %H:%M} ${int(m.monto):,} '
                     f'[{m.estado}] {m.glosa[:40]}').replace(',', '.')
            self.stdout.write(linea)
