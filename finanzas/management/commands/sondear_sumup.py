# -*- coding: utf-8 -*-
"""Sonda de la API de SumUp (P-22 F5, solo LECTURA): imprime la estructura
real de las respuestas para calibrar el conector sin adivinar formatos —
la misma disciplina de las cartolas.

Corre en la Shell de Render (necesita SUMUP_API_KEY en el ambiente):

    python manage.py sondear_sumup
"""
import json
import os
from datetime import date, timedelta

import requests
from django.core.management.base import BaseCommand

BASE = 'https://api.sumup.com'


class Command(BaseCommand):
    help = 'Consulta de solo lectura a la API de SumUp e imprime las estructuras.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=14)

    def handle(self, *args, **opts):
        clave = os.environ.get('SUMUP_API_KEY')
        if not clave:
            self.stderr.write('SUMUP_API_KEY no está en el ambiente.')
            return
        cab = {'Authorization': f'Bearer {clave}'}
        desde = (date.today() - timedelta(days=opts['dias'])).isoformat()
        hasta = date.today().isoformat()

        def sondear(nombre, ruta, params=None):
            self.stdout.write(f'\n── {nombre} · GET {ruta}')
            try:
                r = requests.get(f'{BASE}{ruta}', headers=cab,
                                 params=params or {}, timeout=30)
            except Exception as e:
                self.stdout.write(f'   ERROR de red: {e}')
                return
            self.stdout.write(f'   HTTP {r.status_code}')
            if r.status_code != 200:
                self.stdout.write('   cuerpo: ' + r.text[:300])
                return
            datos = r.json()
            if isinstance(datos, dict):
                self.stdout.write('   claves: ' + ', '.join(sorted(datos.keys())))
                items = (datos.get('items') or datos.get('transactions')
                         or datos.get('payouts') or [])
            else:
                items = datos
            if isinstance(items, list):
                self.stdout.write(f'   items: {len(items)}')
                for it in items[:2]:
                    self.stdout.write('   ejemplo: ' +
                                      json.dumps(it, ensure_ascii=False)[:500])

        sondear('Perfil', '/v0.1/me')
        sondear('Transacciones (historial)', '/v0.1/me/transactions/history',
                {'limit': 3, 'order': 'descending'})
        sondear('Financials: transacciones',
                '/v0.1/me/financials/transactions',
                {'start_date': desde, 'end_date': hasta})
        sondear('Financials: payouts (depósitos)',
                '/v0.1/me/financials/payouts',
                {'start_date': desde, 'end_date': hasta})
        self.stdout.write(self.style.SUCCESS(
            '\nSonda completa. Pegar TODO este output a Claude para calibrar '
            'el conector.'))
