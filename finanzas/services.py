# -*- coding: utf-8 -*-
"""Servicios de finanzas: consumidores automáticos de datos de otras fuentes.

P-22 F2-B: el fetch de la conciliación (`conciliacion.services_mp.traer_pagos_mp`)
separa los pagos donde Aremko COBRA de los donde Aremko PAGA. Los segundos son
ruido para la cola de Deborah, pero para finanzas son exactamente los gastos
pagados vía Mercado Pago — un solo fetch, dos consumidores.
"""
import logging
from datetime import date

from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

# Decisión de Jorge 2026-08-08: la cobertura de gastos parte en julio 2026, el
# primer mes completo y que se recuerda. Aplica igual a lo que llega por API.
COBERTURA_GASTOS_DESDE = date(2026, 7, 1)

# payment_type_id de MP → clave de CuentaFinanciera: CON QUÉ PLATA se pagó.
# Si la compra se fondeó con la Visa, el gasto es de la Visa (el saldo de MP no
# se movió) — importa para que el cierre por saldos (F4) cuadre por cuenta.
CUENTA_POR_PAYMENT_TYPE = {
    'account_money': 'mercado_pago',
    'credit_card': 'visa_2936',
}


def registrar_compras_mp(pagos_api):
    """Convierte pagos de /v1/payments/search donde Aremko es el PAGADOR en
    MovimientoFinanciero de gasto (categoría «Por clasificar», fuente api).

    Idempotente por referencia ``mp:<payment_id>``. Devuelve cuántos gastos
    creó. NUNCA lanza: un problema acá no puede romper el fetch de Deborah —
    el que llama ya envuelve en try/except, y acá además se aísla por pago.
    """
    from .models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero

    try:
        cuentas = {c.clave: c for c in CuentaFinanciera.objects.all()}
        cat = CategoriaFinanciera.objects.get(clave='por_clasificar')
    except CategoriaFinanciera.DoesNotExist:
        logger.warning('finanzas sin sembrar: compras MP no registradas')
        return 0

    creados = 0
    for p in pagos_api:
        try:
            pid = str(p.get('id') or '')
            monto = int(p.get('transaction_amount') or 0)
            if not pid or monto <= 0:
                continue
            f = parse_datetime(p.get('date_approved') or p.get('date_created') or '')
            if not f or f.date() < COBERTURA_GASTOS_DESDE:
                continue
            ref = f'mp:{pid}'
            if MovimientoFinanciero.objects.filter(referencia=ref).exists():
                continue
            clave = CUENTA_POR_PAYMENT_TYPE.get(p.get('payment_type_id'), 'mercado_pago')
            cuenta = cuentas.get(clave)
            if cuenta is None:
                logger.warning('compra MP %s: cuenta %s no sembrada', pid, clave)
                continue
            MovimientoFinanciero.objects.create(
                fecha=f.date(), cuenta=cuenta, clase='gasto', sentido='sale',
                monto=monto, categoria=cat, fuente='api', referencia=ref,
                descripcion=f"Compra vía MP: {p.get('description') or 'sin glosa'}"[:255],
            )
            creados += 1
        except Exception:
            logger.exception('compra MP %s no registrada', p.get('id'))

    if creados:
        logger.info('finanzas: %s compras MP registradas como gasto por clasificar', creados)
    return creados
