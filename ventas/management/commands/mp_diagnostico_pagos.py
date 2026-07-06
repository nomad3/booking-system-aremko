# -*- coding: utf-8 -*-
"""Diagnóstico de SOLO LECTURA contra la API de Mercado Pago (Conciliador F0).

Responde LA pregunta clave del Conciliador: ¿qué pagos ve la API de MP?
En particular, si las TRANSFERENCIAS directas a la Cuenta Vista aparecen en
/v1/payments/search (si aparecen → conciliamos todo directo desde Django,
sin depender de Gmail; si no → Gmail sigue siendo la fuente para transferencias).

No escribe nada (ni en MP ni en la BD). PII enmascarada en la salida (los
nombres/emails salen parciales) para poder pegar el resultado en el chat.

Uso (Render Shell):
    python manage.py mp_diagnostico_pagos
    python manage.py mp_diagnostico_pagos --dias 60 --max 100
"""
import requests
from collections import Counter
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


def _mask(texto):
    """'Maria Perez' → 'Ma*** Pe***'; 'maria@gmail.com' → 'ma***@gm***'."""
    if not texto:
        return '(vacío)'
    partes = str(texto).split('@')
    if len(partes) == 2:  # email
        return f"{partes[0][:2]}***@{partes[1][:2]}***"
    return ' '.join(f"{p[:2]}***" for p in str(texto).split()[:3])


class Command(BaseCommand):
    help = "SOLO LECTURA: lista qué pagos ve la API de MP (¿aparecen las transferencias a la Cuenta Vista?)"

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=30, help='Ventana hacia atrás (default 30)')
        parser.add_argument('--max', type=int, default=50, help='Máximo de pagos a listar (default 50)')
        parser.add_argument('--detalle', type=int, default=0,
                            help='Sondear el DETALLE de N transferencias bancarias (GET /v1/payments/{id}): '
                                 'qué campos trae para identificar al remitente (RUT/nombre)')

    def handle(self, *args, **opts):
        token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', None)
        if not token:
            self.stdout.write(self.style.ERROR(
                'MERCADOPAGO_ACCESS_TOKEN no configurado (agregar env var en Render y redeploy).'))
            return

        desde = timezone.now() - timezone.timedelta(days=opts['dias'])
        params = {
            'sort': 'date_created',
            'criteria': 'desc',
            'range': 'date_created',
            'begin_date': desde.strftime('%Y-%m-%dT%H:%M:%S.000-04:00'),
            'end_date': timezone.now().strftime('%Y-%m-%dT%H:%M:%S.000-04:00'),
            'limit': min(opts['max'], 100),
        }
        r = requests.get(
            'https://api.mercadopago.com/v1/payments/search',
            headers={'Authorization': f'Bearer {token}'},
            params=params, timeout=30,
        )
        self.stdout.write(f"HTTP {r.status_code} · /v1/payments/search · últimos {opts['dias']} días")
        if r.status_code != 200:
            self.stdout.write(self.style.ERROR(r.text[:400]))
            return

        data = r.json()
        total = data.get('paging', {}).get('total', 0)
        resultados = data.get('results', [])
        self.stdout.write(self.style.SUCCESS(
            f"Total en la ventana: {total} · listados: {len(resultados)}\n"))

        tipos = Counter()
        for p in resultados:
            tipos[(p.get('operation_type'), p.get('payment_type_id'), p.get('status'))] += 1

        self.stdout.write('=== Resumen por (operation_type, payment_type, status) ===')
        for (op, pt, st), n in tipos.most_common():
            self.stdout.write(f'  {n:>3} × {op} / {pt} / {st}')

        self.stdout.write('\n=== Detalle (PII enmascarada) ===')
        for p in resultados:
            payer = p.get('payer') or {}
            fecha = (p.get('date_approved') or p.get('date_created') or '')[:16]
            self.stdout.write(
                f"  {fecha} · ${int(p.get('transaction_amount') or 0):,} · "
                f"{p.get('operation_type')}/{p.get('payment_type_id')} · {p.get('status')} · "
                f"ref={p.get('external_reference') or '—'} · "
                f"pagador: {_mask(payer.get('email'))}"
            )

        self.stdout.write(self.style.SUCCESS(
            '\nClave a mirar: si las transferencias a la Cuenta Vista aparecen '
            '(operation_type=money_transfer o payment_type=bank_transfer) → '
            'conciliación 100% vía API, sin Gmail.'))

        # ── Sondeo de DETALLE: ¿el pago trae la identidad del remitente? ──
        # En /payments/search las bank_transfer salen con el email de la PROPIA
        # cuenta como "payer"; acá vemos si GET /v1/payments/{id} trae RUT/nombre
        # del que transfirió (define si el matcher puede usar identidad o solo
        # monto+fecha).
        if opts['detalle']:
            self.stdout.write('\n=== DETALLE de transferencias bancarias (identidad del remitente) ===')
            bancarias = [p for p in resultados if p.get('payment_type_id') == 'bank_transfer'][:opts['detalle']]
            for p in bancarias:
                pid = p.get('id')
                rd = requests.get(
                    f'https://api.mercadopago.com/v1/payments/{pid}',
                    headers={'Authorization': f'Bearer {token}'}, timeout=30,
                )
                self.stdout.write(f'\n--- pago {pid} · HTTP {rd.status_code} ---')
                if rd.status_code != 200:
                    self.stdout.write(rd.text[:200])
                    continue
                d = rd.json()
                self.stdout.write(f"  descripcion: {d.get('description') or '—'}")
                self.stdout.write(f"  external_reference: {d.get('external_reference') or '—'}")
                self.stdout.write(
                    f"  monto: ${int(d.get('transaction_amount') or 0):,} · "
                    f"fecha: {(d.get('date_approved') or '')[:16]}")
                self._dump_identidad('payer', d.get('payer'))
                self._dump_identidad('additional_info', d.get('additional_info'))
                self._dump_identidad('counterpart', d.get('counterpart'))
                td = {k: v for k, v in (d.get('transaction_details') or {}).items()
                      if v not in (None, '', 0)}
                self.stdout.write(f'  transaction_details: {td}')
                poi = (d.get('point_of_interaction') or {}).get('type')
                self.stdout.write(f'  point_of_interaction: {poi}')
                otros = sorted(k for k, v in d.items() if v not in (None, '', [], {}) and k not in (
                    'payer', 'additional_info', 'transaction_details', 'point_of_interaction',
                    'description', 'external_reference', 'transaction_amount', 'date_approved'))
                self.stdout.write(f"  otros campos con datos: {', '.join(otros)}")

    MASK_KEYS = ('email', 'first_name', 'last_name', 'name', 'number', 'nombre')

    def _dump_identidad(self, etiqueta, d):
        """Imprime un dict anidado enmascarando los valores de identidad."""
        if not d:
            self.stdout.write(f'  {etiqueta}: (vacío)')
            return

        def limpiar(x):
            if isinstance(x, dict):
                return {k: (_mask(v) if v and any(m in k.lower() for m in Command.MASK_KEYS)
                            else limpiar(v))
                        for k, v in x.items() if v not in (None, '', [], {})}
            if isinstance(x, list):
                return [limpiar(i) for i in x]
            return x

        self.stdout.write(f'  {etiqueta}: {limpiar(d)}')
