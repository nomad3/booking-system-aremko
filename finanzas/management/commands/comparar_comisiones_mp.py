# -*- coding: utf-8 -*-
"""¿Por qué subió la comisión de Mercado Pago? (pregunta de Jorge 2026-08-10)

En julio los cobros se movieron de «Mercado Pago» a «Mercado Pago (link)» y la
sospecha es que los clientes están pagando en cuotas, donde MP cobra más. Este
comando trae los pagos de la API mes a mes y muestra la comisión EFECTIVA (%)
por método y por número de cuotas, que es lo único que responde la pregunta:
un monto de comisión más alto puede ser solo más ventas.

SOLO LECTURA: no escribe nada en la base.

    python manage.py comparar_comisiones_mp --desde 2026-06-01 --hasta 2026-07-31
"""
from collections import defaultdict
from datetime import datetime, timedelta

import requests
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


def _clp(n):
    return '$' + format(int(round(n)), ',d').replace(',', '.')


def _pct(parte, total):
    return f'{(parte / total * 100):.2f}%' if total else '—'


def comision_de(pago):
    """Lo que MP se quedó de este cobro.

    `fee_details` trae varios conceptos (mercadopago_fee, financing_fee…) y
    los que paga el cliente vienen con fee_payer='payer' — esos no son costo
    nuestro. Se suman solo los que paga el vendedor.
    """
    total = 0.0
    for f in pago.get('fee_details') or []:
        if (f.get('fee_payer') or 'collector') == 'collector':
            total += float(f.get('amount') or 0)
    return total


class Command(BaseCommand):
    help = 'Compara la comisión efectiva de Mercado Pago entre períodos.'

    def add_arguments(self, parser):
        parser.add_argument('--desde', default='2026-06-01')
        parser.add_argument('--hasta', default='2026-07-31')
        parser.add_argument('--detalle', action='store_true',
                            help='Lista los cobros con comisión más alta.')

    def handle(self, *args, **opts):
        from conciliacion.services_mp import es_cobro_nuestro, id_cuenta_mp

        token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', None)
        if not token:
            self.stderr.write('Falta MERCADOPAGO_ACCESS_TOKEN')
            return
        mi_id = id_cuenta_mp(token)

        desde = datetime.strptime(opts['desde'], '%Y-%m-%d')
        hasta = datetime.strptime(opts['hasta'], '%Y-%m-%d') + timedelta(days=1)

        pagos = self._traer(token, desde, hasta)
        # Solo COBROS nuestros: las compras que Aremko paga con MP tienen su
        # propia comisión y no son ingreso.
        cobros = [p for p in pagos if es_cobro_nuestro(p, mi_id)]
        self.stdout.write(f'API: {len(pagos)} pagos · cobros nuestros: '
                          f'{len(cobros)}\n')

        por_mes = defaultdict(lambda: {'bruto': 0.0, 'com': 0.0, 'n': 0})
        por_mes_metodo = defaultdict(lambda: {'bruto': 0.0, 'com': 0.0, 'n': 0})
        por_mes_cuotas = defaultdict(lambda: {'bruto': 0.0, 'com': 0.0, 'n': 0})
        caros = []

        for p in cobros:
            crudo = p.get('date_approved') or p.get('date_created') or ''
            if not crudo:
                continue
            mes = crudo[:7]
            bruto = float(p.get('transaction_amount') or 0)
            com = comision_de(p)
            if bruto <= 0:
                continue
            metodo = (p.get('payment_type_id') or '?')
            cuotas = int(p.get('installments') or 1)

            for acumulador, clave in (
                    (por_mes, mes),
                    (por_mes_metodo, (mes, metodo)),
                    (por_mes_cuotas, (mes, cuotas))):
                acumulador[clave]['bruto'] += bruto
                acumulador[clave]['com'] += com
                acumulador[clave]['n'] += 1
            caros.append((com / bruto if bruto else 0, com, bruto, mes,
                          metodo, cuotas, p.get('id')))

        self.stdout.write('\n=== POR MES ===')
        self.stdout.write(f'{"Mes":9} {"Cobros":>7} {"Bruto":>15} '
                          f'{"Comisión":>13} {"% efectivo":>11}')
        for mes in sorted(por_mes):
            d = por_mes[mes]
            self.stdout.write(f'{mes:9} {d["n"]:>7} {_clp(d["bruto"]):>15} '
                              f'{_clp(d["com"]):>13} '
                              f'{_pct(d["com"], d["bruto"]):>11}')

        self.stdout.write('\n=== POR MES Y MÉTODO ===')
        for mes, metodo in sorted(por_mes_metodo):
            d = por_mes_metodo[(mes, metodo)]
            self.stdout.write(
                f'{mes}  {metodo:16} {d["n"]:>4} cobros  '
                f'{_clp(d["bruto"]):>14}  com {_clp(d["com"]):>11}  '
                f'{_pct(d["com"], d["bruto"]):>8}')

        self.stdout.write('\n=== POR MES Y CUOTAS (la hipótesis) ===')
        for mes, cuotas in sorted(por_mes_cuotas):
            d = por_mes_cuotas[(mes, cuotas)]
            self.stdout.write(
                f'{mes}  {cuotas:>2} cuota(s)  {d["n"]:>4} cobros  '
                f'{_clp(d["bruto"]):>14}  com {_clp(d["com"]):>11}  '
                f'{_pct(d["com"], d["bruto"]):>8}')

        sin_com = [c for c in caros if c[1] == 0]
        if sin_com:
            metodos = defaultdict(int)
            for c in sin_com:
                metodos[c[4]] += 1
            resumen = ' · '.join(f'{m}: {n}' for m, n in sorted(metodos.items()))
            self.stdout.write(f'\nCobros SIN comisión: {len(sin_com)} '
                              f'({resumen})')

        if opts['detalle']:
            self.stdout.write('\n=== LOS 15 CON MAYOR % DE COMISIÓN ===')
            for tasa, com, bruto, mes, metodo, cuotas, pid in \
                    sorted(caros, reverse=True)[:15]:
                self.stdout.write(
                    f'  {mes} {metodo:14} {cuotas:>2}c  bruto {_clp(bruto):>12}'
                    f'  com {_clp(com):>10}  {tasa * 100:5.2f}%  id {pid}')

    def _traer(self, token, desde, hasta):
        """Pagina la búsqueda de pagos aprobados del rango pedido."""
        pagos, offset = [], 0
        while True:
            r = requests.get(
                'https://api.mercadopago.com/v1/payments/search',
                headers={'Authorization': f'Bearer {token}'},
                params={
                    'sort': 'date_created', 'criteria': 'asc',
                    'range': 'date_created',
                    'begin_date': desde.strftime('%Y-%m-%dT00:00:00.000-04:00'),
                    'end_date': hasta.strftime('%Y-%m-%dT00:00:00.000-04:00'),
                    'status': 'approved',
                    'limit': 50, 'offset': offset,
                },
                timeout=45,
            )
            r.raise_for_status()
            data = r.json()
            page = data.get('results', [])
            pagos.extend(page)
            total = data.get('paging', {}).get('total', 0)
            offset += len(page)
            self.stdout.write(f'  … {offset}/{total}', ending='\r')
            if not page or offset >= total or offset >= 3000:
                break
        self.stdout.write('')
        return pagos
