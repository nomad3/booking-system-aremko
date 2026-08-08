# -*- coding: utf-8 -*-
"""Saca de la cola del Conciliador los MovimientoMP que no son cobros de Aremko.

Hasta el 2026-08-08 `traer_pagos_mp()` guardaba TODO lo que devolvia
`/v1/payments/search`, que incluye los pagos donde Aremko es el pagador: compras
por Mercado Libre, retail, etc. Esos movimientos no tienen ninguna reserva a la
cual aplicarse, asi que se acumulaban en la cola de Deborah como ruido.

El fetch ya quedo filtrado por `collector_id`. Este comando limpia lo que entro
antes de ese arreglo.

Como decide: vuelve a pedirle a la API el mismo rango de fechas y arma el
conjunto de pagos donde Aremko SI cobra. Todo MovimientoMP del rango que no este
en ese conjunto es ajeno. Se decide contra la API, no adivinando por la glosa.

Modo LECTURA por defecto: lista lo que haria y no escribe nada. Con --aplicar
los marca 'ignorado' con el motivo escrito, para que nadie tenga que reconstruir
despues por que salieron de la cola.

    python manage.py limpiar_movimientos_ajenos --dias 75
    python manage.py limpiar_movimientos_ajenos --dias 75 --aplicar
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

MOTIVO = 'No es un cobro: en Mercado Pago Aremko figura como pagador'


class Command(BaseCommand):
    help = 'Marca como ignorados los MovimientoMP que no son cobros de Aremko.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=75,
                            help='Ventana hacia atras a revisar (default 75).')
        parser.add_argument('--aplicar', action='store_true',
                            help='Escribe los cambios. Sin esto solo informa.')

    def handle(self, *args, **opts):
        import requests
        from conciliacion.models import MovimientoMP
        from conciliacion.services_mp import id_cuenta_mp, es_cobro_nuestro

        dias, aplicar = opts['dias'], opts['aplicar']
        token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', None)
        if not token:
            self.stderr.write('MERCADOPAGO_ACCESS_TOKEN no configurado')
            return

        mi_id = id_cuenta_mp(token)
        desde = timezone.now() - timedelta(days=dias)

        # Mismo recorrido que el fetch: se pagina hasta agotar o hasta 500.
        cobros, offset, total = set(), 0, 0
        while True:
            r = requests.get(
                'https://api.mercadopago.com/v1/payments/search',
                headers={'Authorization': f'Bearer {token}'},
                params={
                    'sort': 'date_created', 'criteria': 'desc',
                    'range': 'date_created',
                    'begin_date': desde.strftime('%Y-%m-%dT%H:%M:%S.000-04:00'),
                    'end_date': timezone.now().strftime('%Y-%m-%dT%H:%M:%S.000-04:00'),
                    'status': 'approved',
                    'limit': 50, 'offset': offset,
                },
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            page = data.get('results', [])
            for p in page:
                total += 1
                if es_cobro_nuestro(p, mi_id):
                    cobros.add(str(p.get('id')))
            offset += len(page)
            if not page or offset >= data.get('paging', {}).get('total', 0) or offset >= 500:
                break

        # Si la API no devolvio nada, cortar: marcar todo como ajeno seria un
        # desastre silencioso provocado por una caida de red.
        if not total:
            self.stderr.write('La API no devolvio pagos. No se toca nada.')
            return

        en_rango = MovimientoMP.objects.filter(fecha__gte=desde)
        ajenos = [m for m in en_rango if m.mp_payment_id not in cobros]

        self.stdout.write(f'API: {total} pagos en la ventana, {len(cobros)} son cobros de Aremko')
        self.stdout.write(f'Base: {en_rango.count()} movimientos en el mismo rango')
        self.stdout.write(f'A sacar de la cola: {len(ajenos)}\n')

        if not ajenos:
            self.stdout.write('Nada que limpiar.')
            return

        por_estado, monto = {}, 0
        for m in ajenos:
            por_estado[m.estado] = por_estado.get(m.estado, 0) + 1
            monto += int(m.monto)
        self.stdout.write('Por estado actual: ' + ', '.join(
            f'{k}={v}' for k, v in sorted(por_estado.items())))
        self.stdout.write(f'Monto total involucrado: {monto:,}\n'.replace(',', '.'))

        for m in sorted(ajenos, key=lambda x: x.fecha, reverse=True)[:25]:
            self.stdout.write(
                f'  {str(m.fecha)[:10]}  {int(m.monto):>9,}'.replace(',', '.')
                + f'  {m.estado:<10} {(m.glosa or "(sin glosa)")[:46]}')
        if len(ajenos) > 25:
            self.stdout.write(f'  ... y {len(ajenos) - 25} mas')

        # Los ya aplicados NO se tocan: si alguno se aplico a una reserva, sacarlo
        # de la cola dejaria un pago registrado sin su movimiento de respaldo.
        aplicados = [m for m in ajenos if m.estado == 'aplicado']
        if aplicados:
            self.stdout.write(self.style.WARNING(
                f'\n{len(aplicados)} ya estan APLICADOS a una reserva: se dejan como estan. '
                'Revisar a mano — un cobro ajeno no deberia haberse aplicado.'))
        tocar = [m for m in ajenos if m.estado != 'aplicado']

        if not aplicar:
            self.stdout.write(self.style.WARNING(
                f'\nMODO LECTURA. Con --aplicar se marcarian {len(tocar)} como ignorado.'))
            return

        for m in tocar:
            m.estado = 'ignorado'
            m.sugerencia_motivo = MOTIVO
        MovimientoMP.objects.bulk_update(tocar, ['estado', 'sugerencia_motivo'])
        self.stdout.write(self.style.SUCCESS(
            f'\nListo: {len(tocar)} movimientos fuera de la cola.'))
