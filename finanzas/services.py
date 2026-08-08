# -*- coding: utf-8 -*-
"""Servicios de finanzas: consumidores automáticos de datos de otras fuentes.

P-22 F2-B: el fetch de la conciliación (`conciliacion.services_mp.traer_pagos_mp`)
separa los pagos donde Aremko COBRA de los donde Aremko PAGA. Los segundos son
ruido para la cola de Deborah, pero para finanzas son exactamente los gastos
pagados vía Mercado Pago — un solo fetch, dos consumidores.

P-22 F3: las transferencias SALIENTES de MP (pagos a trabajadores, barridos a
Scotiabank) no aparecen en /v1/payments/search — pero MP manda un correo por
cada una («Tu transferencia fue enviada», a abonosaremko, reenviado a ecolonco
por el filtro del 2026-08-06). `parsear_transferencia_mp` +
`registrar_transferencia_mp` convierten ese correo en el movimiento.
"""
import hashlib
import html as html_lib
import logging
import re
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


# ── F3: transferencias salientes de Mercado Pago, desde el correo ────────────

def _texto_plano(html_crudo):
    """HTML del correo → texto plano de una línea (tags fuera, entidades resueltas)."""
    txt = re.sub(r'<[^>]+>', ' ', html_crudo or '')
    txt = html_lib.unescape(txt)
    return re.sub(r'\s+', ' ', txt).strip()


def parsear_transferencia_mp(html_crudo):
    """Extrae monto/beneficiario/entidad del correo «Tu transferencia fue enviada».

    Función pura (testeable sin red). Formato real verificado 2026-08-08:
    «Ya enviamos tu transferencia de $ 10.000 … Datos del beneficiario
    Nombre y apellido: Martin Aguilera Entidad: Banco Estado Número de cuenta: …»
    Devuelve None si el correo no calza — mejor no registrar que adivinar.
    """
    txt = _texto_plano(html_crudo)
    m = re.search(r'transferencia de\s*\$\s*([\d.]+)', txt)
    b = re.search(r'Nombre y apellido:\s*(.*?)\s*Entidad:', txt)
    if not m or not b:
        return None
    monto = int(m.group(1).replace('.', ''))
    if monto <= 0 or not b.group(1).strip():
        return None
    e = re.search(r'Entidad:\s*(.*?)\s*N[úu]mero de cuenta:', txt)
    return {'monto': monto, 'beneficiario': b.group(1).strip(),
            'entidad': e.group(1).strip() if e else ''}


def referencia_correo(message_id, respaldo=''):
    """Referencia idempotente para un correo: hash del Message-ID (estable)."""
    base = (message_id or respaldo or '').strip()
    return 'correo:mp:' + hashlib.sha1(base.encode()).hexdigest()[:24]


def registrar_transferencia_mp(datos, fecha, referencia):
    """Crea el/los MovimientoFinanciero de una transferencia saliente de MP.

    Clasificación (las mismas reglas validadas con Jorge para el histórico):
    - beneficiario con «aremko» → TRASPASO MP→Scotiabank, dos piernas enlazadas
    - «insumos sur» → gasto insumos · resto → gasto remuneraciones

    Guardias: idempotencia por referencia, y anti-solape con la carga histórica
    (si existe un hist:mp con la misma fecha+monto, este correo ya está cargado).
    Devuelve ('creado'|'ya_existe'|'en_historico', movimientos_creados).
    """
    from django.db import transaction

    from .models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero

    if MovimientoFinanciero.objects.filter(
            referencia__in=(referencia, f'{referencia}:sale')).exists():
        return 'ya_existe', 0
    if MovimientoFinanciero.objects.filter(
            referencia__startswith='hist:mp', fecha=fecha,
            monto=datos['monto']).exists():
        return 'en_historico', 0

    cuentas = {c.clave: c for c in CuentaFinanciera.objects.all()}
    benef = datos['beneficiario']
    with transaction.atomic():
        if 'aremko' in benef.lower():
            sale = MovimientoFinanciero.objects.create(
                fecha=fecha, cuenta=cuentas['mercado_pago'], clase='traspaso',
                sentido='sale', monto=datos['monto'], fuente='correo',
                referencia=f'{referencia}:sale',
                descripcion='Barrido MP → Scotiabank (correo)')
            entra = MovimientoFinanciero.objects.create(
                fecha=fecha, cuenta=cuentas['scotiabank'], clase='traspaso',
                sentido='entra', monto=datos['monto'], fuente='correo',
                referencia=f'{referencia}:entra', traspaso_par=sale,
                descripcion='Barrido MP → Scotiabank (correo)')
            sale.traspaso_par = entra
            sale.save(update_fields=['traspaso_par'])
            return 'creado', 2

        clave_cat = 'insumos' if 'insumos sur' in benef.lower() else 'remuneraciones'
        MovimientoFinanciero.objects.create(
            fecha=fecha, cuenta=cuentas['mercado_pago'], clase='gasto',
            sentido='sale', monto=datos['monto'],
            categoria=CategoriaFinanciera.objects.get(clave=clave_cat),
            fuente='correo', referencia=referencia,
            descripcion=f'Transferencia MP a {benef}'[:255])
        return 'creado', 1
