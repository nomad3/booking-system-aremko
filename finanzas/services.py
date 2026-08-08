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


# ── F4 paso 2: comisiones que MP descuenta por cada cobro ────────────────────

def _comision_cobro_mp(pago):
    """Comisión total que paga Aremko (collector) en un pago, en CLP enteros.

    `fee_details` viene por pago en /v1/payments/search; las transferencias
    simples suelen traer 0 y los cobros con tarjeta/link el % de MP.
    """
    total = 0.0
    for f in (pago.get('fee_details') or []):
        if (f.get('fee_payer') or 'collector') == 'collector':
            total += float(f.get('amount') or 0)
    return int(round(total))


def registrar_comisiones_mp(cobros_api):
    """Registra la comisión de cada cobro MP como gasto «comisiones» (fuente api).

    Sin esto el saldo MP calculado queda inflado: los cobros entran BRUTOS al
    registro comercial, pero a la cuenta le llega el neto. Idempotente por
    referencia mp:fee:<payment_id>; respeta el corte de julio. Nunca lanza.
    """
    from .models import CategoriaFinanciera, CuentaFinanciera, MovimientoFinanciero

    try:
        cuenta = CuentaFinanciera.objects.get(clave='mercado_pago')
        cat = CategoriaFinanciera.objects.get(clave='comisiones')
    except (CuentaFinanciera.DoesNotExist, CategoriaFinanciera.DoesNotExist):
        logger.warning('finanzas sin sembrar: comisiones MP no registradas')
        return 0

    creados = 0
    for p in cobros_api:
        try:
            pid = str(p.get('id') or '')
            monto = _comision_cobro_mp(p)
            if not pid or monto <= 0:
                continue
            f = parse_datetime(p.get('date_approved') or p.get('date_created') or '')
            if not f or f.date() < COBERTURA_GASTOS_DESDE:
                continue
            ref = f'mp:fee:{pid}'
            if MovimientoFinanciero.objects.filter(referencia=ref).exists():
                continue
            MovimientoFinanciero.objects.create(
                fecha=f.date(), cuenta=cuenta, clase='gasto', sentido='sale',
                monto=monto, categoria=cat, fuente='api', referencia=ref,
                descripcion=f"Comisión MP del cobro {pid} ({p.get('description') or 'sin glosa'})"[:255])
            creados += 1
        except Exception:
            logger.exception('comisión MP %s no registrada', p.get('id'))

    if creados:
        logger.info('finanzas: %s comisiones MP registradas', creados)
    return creados


# ── F4 paso 3: cartola BancoEstado (export XLSX del portal) ──────────────────
# Formato real verificado 2026-08-08 (Excel_Cartola_Historica_Chequera_
# Electronica.xlsx): hoja "Resumen" con rótulos en col A y valores en col E;
# hoja "Movimientos" con encabezado Fecha DD/MM (sin año — el año sale del
# rango del Resumen) | ... | Descripción | Cheques / Cargos | Depósitos /
# Abonos | Saldo (encadenado fila a fila). Montos mezclados: enteros crudos
# y strings '$1.234.567'.

CATEGORIAS_CARTOLA = {
    # clave → (nombre, clase). Se crean al confirmar si no existen (sin Shell).
    'liquidacion_flow': ('Liquidación Flow', 'ingreso'),
    'liquidacion_sumup': ('Liquidación SumUp', 'ingreso'),
    'transferencias_recibidas': ('Transferencias recibidas', 'ingreso'),
}


def _monto_celda(v):
    if v is None:
        return 0
    if isinstance(v, (int, float)):
        return int(round(v))
    s = str(v).replace('$', '').replace('.', '').replace(' ', '').strip()
    return int(s) if s.lstrip('-').isdigit() else 0


def clasificar_fila_cartola(descripcion, cargo, abono):
    """(clase, sentido, categoria_clave) para una fila de la cartola."""
    d = (descripcion or '').upper()
    if abono > 0:
        if 'SUMUP' in d:
            return 'ingreso', 'entra', 'liquidacion_sumup'
        if 'FLOW' in d:
            return 'ingreso', 'entra', 'liquidacion_flow'
        return 'ingreso', 'entra', 'transferencias_recibidas'
    return 'gasto', 'sale', 'por_clasificar'


def parsear_cartola_bancoestado(archivo):
    """Lee el XLSX del portal y devuelve dict con resumen, filas y chequeos.

    No escribe nada. Cada fila queda con su referencia idempotente
    be:<hash(fecha|descripcion|cargo|abono|saldo)> — el saldo encadenado hace
    única incluso a la segunda transferencia idéntica del mismo día.
    """
    import warnings
    from datetime import datetime

    import openpyxl

    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        wb = openpyxl.load_workbook(archivo, data_only=True, read_only=True)

    if 'Resumen' not in wb.sheetnames or 'Movimientos' not in wb.sheetnames:
        raise ValueError('El archivo no tiene las hojas Resumen y Movimientos '
                         'del export de BancoEstado.')

    # ── Resumen: rótulo en col A, valor en la primera celda no vacía después ──
    resumen = {}
    for fila in wb['Resumen'].iter_rows(values_only=True):
        rotulo = str(fila[0] or '').strip()
        if not rotulo:
            continue
        valor = next((c for c in fila[1:] if c is not None), None)
        resumen[rotulo] = valor

    def _fecha_resumen(rotulo):
        crudo = str(resumen.get(rotulo) or '').strip()
        return datetime.strptime(crudo, '%d/%m/%Y').date()

    try:
        f_inicio = _fecha_resumen('Fecha Inicio')
        f_final = _fecha_resumen('Fecha Final')
    except ValueError:
        raise ValueError('El Resumen no trae Fecha Inicio/Fecha Final — '
                         '¿es el export correcto?')
    saldo_inicial = _monto_celda(resumen.get('Saldo Inicial'))
    saldo_final_resumen = _monto_celda(resumen.get('Saldo Final'))

    # ── Movimientos ──────────────────────────────────────────────────────────
    ws = wb['Movimientos']
    filas_crudas = list(ws.iter_rows(values_only=True))
    if not filas_crudas:
        raise ValueError('La hoja Movimientos viene vacía.')
    encabezado = [str(c or '') for c in filas_crudas[0]]

    def _col(nombre):
        for i, h in enumerate(encabezado):
            if nombre.lower() in h.lower():
                return i
        raise ValueError(f'No encuentro la columna «{nombre}» en Movimientos.')

    c_fecha, c_desc = _col('Fecha'), _col('Descripción')
    c_cargo, c_abono, c_saldo = _col('Cargos'), _col('Abonos'), _col('Saldo')

    filas, saldo_prev, cadena_rota = [], saldo_inicial, 0
    anio, mes_prev = f_inicio.year, f_inicio.month
    for cruda in filas_crudas[1:]:
        crudo_fecha = cruda[c_fecha]
        if crudo_fecha is None:
            continue
        if hasattr(crudo_fecha, 'year'):          # celda ya viene como fecha
            fecha = crudo_fecha.date() if hasattr(crudo_fecha, 'date') else crudo_fecha
        else:
            try:
                dia, mes = (int(x) for x in str(crudo_fecha).strip().split('/')[:2])
            except ValueError:
                continue
            if mes < mes_prev:                    # cruce de año (dic → ene)
                anio += 1
            mes_prev = mes
            fecha = date(anio, mes, dia)

        desc = str(cruda[c_desc] or '').strip()
        cargo, abono = _monto_celda(cruda[c_cargo]), _monto_celda(cruda[c_abono])
        saldo = _monto_celda(cruda[c_saldo])
        if cargo == 0 and abono == 0:
            continue
        if saldo_prev + abono - cargo != saldo:
            cadena_rota += 1
        saldo_prev = saldo

        clase, sentido, cat = clasificar_fila_cartola(desc, cargo, abono)
        huella = f'{fecha.isoformat()}|{desc}|{cargo}|{abono}|{saldo}'
        filas.append({
            'fecha': fecha.isoformat(), 'descripcion': desc,
            'cargo': cargo, 'abono': abono, 'saldo': saldo,
            'clase': clase, 'sentido': sentido, 'categoria': cat,
            'referencia': 'be:' + hashlib.sha1(huella.encode()).hexdigest()[:24],
        })

    # ── Cierres de mes cubiertos por el archivo ──────────────────────────────
    # El saldo de la última fila de un mes ES el cierre de ese mes, siempre que
    # el archivo siga en el mes siguiente (si no, el mes quedó a medias).
    cierres = {}
    for i, f in enumerate(filas):
        mes_fila = f['fecha'][:7]
        hay_despues = any(g['fecha'][:7] > mes_fila for g in filas[i + 1:])
        if hay_despues:
            cierres[mes_fila] = f['saldo']

    return {
        'cuenta_numero': str(resumen.get('N° Cuenta') or ''),
        'fecha_inicio': f_inicio.isoformat(), 'fecha_final': f_final.isoformat(),
        'saldo_inicial': saldo_inicial, 'saldo_final_resumen': saldo_final_resumen,
        'saldo_final_calculado': saldo_prev,
        'total_cargos': sum(f['cargo'] for f in filas),
        'total_abonos': sum(f['abono'] for f in filas),
        'cadena_rota': cadena_rota,
        'cuadra': (cadena_rota == 0 and saldo_prev == saldo_final_resumen),
        'cierres_mes': cierres,
        'filas': filas,
    }


def registrar_filas_cartola(filas, cierres_mes=None, cuenta_clave='bancoestado'):
    """Escribe las filas confirmadas de una cartola (fuente=captura) + cierres.

    Idempotente por referencia; respeta el corte de julio; y re-verifica el
    estado de cada fila (defensa doble contra dobles conteos: histórico
    mes-nivel de Scotiabank, barridos ya registrados como traspaso).
    Devuelve (creados, saltados).
    """
    from django.db import transaction

    from .models import (CategoriaFinanciera, CuentaFinanciera,
                         MovimientoFinanciero, SaldoMensual)

    cuenta = CuentaFinanciera.objects.get(clave=cuenta_clave)
    cats = {c.clave: c for c in CategoriaFinanciera.objects.all()}
    for clave, (nombre, clase) in CATEGORIAS_CARTOLA.items():
        if clave not in cats:
            cats[clave], _ = CategoriaFinanciera.objects.get_or_create(
                clave=clave, defaults={'nombre': nombre, 'clase': clase})

    creados = saltados = 0
    with transaction.atomic():
        for f in filas:
            fecha = date.fromisoformat(f['fecha'])
            monto = f['abono'] or f['cargo']
            if (fecha < COBERTURA_GASTOS_DESDE or monto <= 0
                    or estado_fila_cartola(cuenta_clave, f) != 'nuevo'):
                saltados += 1
                continue
            MovimientoFinanciero.objects.create(
                fecha=fecha, cuenta=cuenta, clase=f['clase'],
                sentido=f['sentido'], monto=monto,
                categoria=cats.get(f['categoria']),
                fuente='captura', referencia=f['referencia'],
                descripcion=f"Cartola {cuenta_clave}: {f['descripcion']}"[:255])
            creados += 1

        for mes_iso, saldo in (cierres_mes or {}).items():
            anio, mes = (int(x) for x in mes_iso.split('-'))
            SaldoMensual.objects.update_or_create(
                cuenta=cuenta, periodo=date(anio, mes, 1),
                defaults={'saldo_cierre': saldo, 'fuente': 'cartola',
                          'notas': 'Cierre derivado del export de cartola'})

    return creados, saltados


# ── F4 paso 3b: cartola Scotiabank (export .xls del portal) ──────────────────
# Formato real verificado 2026-08-08 (typeDesc.xls): hoja única 'Data' con
# metadatos rótulo/valor arriba (Saldo Disponible, Fecha Desde/Hasta) y luego
# encabezado Fecha DD-MM-AAAA | Descripción | Sucursal | N° Doc. | Cargos
# (NEGATIVOS) | Abonos | Saldo — en orden DESCENDENTE (lo más nuevo primero).

RUT_AREMKO_SIN_DV = '76485192'


def clasificar_fila_scotiabank(descripcion, cargo, abono):
    """(clase, sentido, categoria_clave, propio) para una fila Scotiabank."""
    d = (descripcion or '').upper()
    propio = RUT_AREMKO_SIN_DV in d or 'AREMKO' in d
    if abono > 0:
        # Abono propio = barrido desde otra cuenta de Aremko (traspaso, no
        # ingreso). El match contra el traspaso ya registrado se hace aparte.
        if propio:
            return 'traspaso', 'entra', '', True
        return 'ingreso', 'entra', 'transferencias_recibidas', False
    if 'SEGURO' in d:
        return 'gasto', 'sale', 'seguros', False
    if 'COMISION' in d or d.startswith('IVA'):
        return 'gasto', 'sale', 'comisiones', False
    return 'gasto', 'sale', 'por_clasificar', False


def parsear_filas_scotiabank(filas_crudas):
    """Núcleo puro: recibe las filas de la hoja como listas y devuelve el
    mismo shape que la cartola BancoEstado. Testeable sin xlrd.

    Soporta las DOS variantes reales del portal (verificadas 2026-08-08):
    - Movimientos de la línea (typeDesc, 7 columnas, DESCENDENTE, meta
      'Saldo Disponible' / 'Número Línea')
    - Estado de cuenta mensual (6 columnas, ASCENDENTE, meta 'Saldo
      Anterior' / 'Saldo Actual' / 'Numero Cuenta')
    Las columnas se mapean POR NOMBRE del encabezado y el orden se detecta
    comparando la primera y la última fecha.
    """
    from datetime import datetime

    meta, encabezado_en = {}, None
    for i, fila in enumerate(filas_crudas):
        primera = str(fila[0] or '').strip()
        if primera == 'Fecha' and any('Descripci' in str(c or '') for c in fila):
            encabezado_en = i
            break
        if primera and len(fila) > 1 and fila[1] not in ('', None):
            meta[primera] = fila[1]
    if encabezado_en is None:
        raise ValueError('No encuentro el encabezado de movimientos — '
                         '¿es el export de Scotiabank?')

    encabezado = [str(c or '').lower() for c in filas_crudas[encabezado_en]]

    def _col(pedazo):
        for j, h in enumerate(encabezado):
            if pedazo in h:
                return j
        raise ValueError(f'No encuentro la columna «{pedazo}» en el export.')

    c_desc, c_cargo = _col('descripci'), _col('cargo')
    c_abono, c_saldo = _col('abono'), _col('saldo')

    movimientos = []
    for fila in filas_crudas[encabezado_en + 1:]:
        crudo_fecha = str(fila[0] or '').strip()
        if not crudo_fecha:
            continue
        try:
            fecha = datetime.strptime(crudo_fecha, '%d-%m-%Y').date()
        except ValueError:
            continue
        desc = str(fila[c_desc] or '').strip()
        cargo = abs(_monto_celda(fila[c_cargo]))
        abono = _monto_celda(fila[c_abono])
        saldo = _monto_celda(fila[c_saldo])
        if cargo == 0 and abono == 0:
            continue
        movimientos.append((fecha, desc, cargo, abono, saldo))

    # Orden: la variante typeDesc viene de lo más nuevo a lo más viejo; el
    # estado de cuenta mensual ya viene cronológico. Se detecta por fechas.
    if len(movimientos) > 1 and movimientos[0][0] > movimientos[-1][0]:
        movimientos.reverse()

    # Ancla del inicio si la trae la cabecera (estado de cuenta mensual).
    saldo_anterior = _monto_celda(meta.get('Saldo Anterior'))

    filas, cadena_rota = [], 0
    saldo_prev = saldo_anterior if saldo_anterior else None
    for fecha, desc, cargo, abono, saldo in movimientos:
        if saldo_prev is not None and saldo_prev + abono - cargo != saldo:
            cadena_rota += 1
        saldo_prev = saldo
        clase, sentido, cat, propio = clasificar_fila_scotiabank(desc, cargo, abono)
        huella = f'{fecha.isoformat()}|{desc}|{cargo}|{abono}|{saldo}'
        filas.append({
            'fecha': fecha.isoformat(), 'descripcion': desc,
            'cargo': cargo, 'abono': abono, 'saldo': saldo,
            'clase': clase, 'sentido': sentido, 'categoria': cat,
            'propio': propio,
            'referencia': 'sc:' + hashlib.sha1(huella.encode()).hexdigest()[:24],
        })
    if not filas:
        raise ValueError('El export no trae movimientos.')

    saldo_inicial = (saldo_anterior or
                     filas[0]['saldo'] - filas[0]['abono'] + filas[0]['cargo'])
    saldo_final = filas[-1]['saldo']

    cierres = {}
    for i, f in enumerate(filas):
        mes_fila = f['fecha'][:7]
        if any(g['fecha'][:7] > mes_fila for g in filas[i + 1:]):
            cierres[mes_fila] = f['saldo']
    # El estado de cuenta MENSUAL cerrado (Fecha Hasta = último día del mes)
    # también ancla el cierre de ese mes, aunque no haya filas del siguiente.
    hasta = str(meta.get('Fecha Hasta') or '').strip()
    if hasta:
        try:
            from datetime import datetime as _dt
            from datetime import timedelta as _td
            f_hasta = _dt.strptime(hasta, '%d-%m-%Y').date()
            if (f_hasta + _td(days=1)).month != f_hasta.month:
                cierres.setdefault(f'{f_hasta.year}-{f_hasta.month:02d}',
                                   saldo_final)
        except ValueError:
            pass

    # Saldo final declarado por la cabecera, según la variante.
    declarado = (_monto_celda(meta.get('Saldo Disponible')) or
                 _monto_celda(meta.get('Saldo Actual')))
    n_cuenta = meta.get('Número Línea') or meta.get('Numero Cuenta') or ''
    if isinstance(n_cuenta, float) and n_cuenta.is_integer():
        n_cuenta = int(n_cuenta)
    return {
        'cuenta_numero': str(n_cuenta),
        'fecha_inicio': filas[0]['fecha'], 'fecha_final': filas[-1]['fecha'],
        'saldo_inicial': saldo_inicial, 'saldo_final_resumen': declarado or saldo_final,
        'saldo_final_calculado': saldo_final,
        'total_cargos': sum(f['cargo'] for f in filas),
        'total_abonos': sum(f['abono'] for f in filas),
        'cadena_rota': cadena_rota,
        'cuadra': (cadena_rota == 0 and
                   (not declarado or declarado == saldo_final)),
        'cierres_mes': cierres,
        'filas': filas,
    }


def parsear_cartola_scotiabank(archivo):
    """Capa fina: lee el .xls con xlrd y delega en el núcleo puro."""
    import xlrd

    wb = xlrd.open_workbook(file_contents=archivo.read())
    hoja = wb.sheet_by_index(0)
    crudas = [[hoja.cell_value(i, j) for j in range(hoja.ncols)]
              for i in range(hoja.nrows)]
    return parsear_filas_scotiabank(crudas)


def estado_fila_cartola(cuenta_clave, fila):
    """'nuevo' | 'ya_existe' | 'en_historico' | 'revisar' para una fila.

    La usan la vista previa (mostrar) Y el registro (defensa doble):
    - referencia ya escrita → ya_existe
    - Scotiabank, gasto: el histórico de julio era mes-nivel con fecha
      estimada → cualquier hist: del MISMO MES con el mismo monto lo cubre
      (conservador: mejor saltar que contar dos veces).
    - BancoEstado: hist: exacto por fecha+monto.
    - Traspaso propio (barrido que llega): si ya existe la pierna 'entra'
      con el mismo monto a ±2 días → ya_existe; si no → 'revisar' (no se
      crea una pierna suelta que rompería la suma cero).
    """
    from .models import MovimientoFinanciero

    fecha = date.fromisoformat(fila['fecha'])
    monto = fila['abono'] or fila['cargo']

    if MovimientoFinanciero.objects.filter(referencia=fila['referencia']).exists():
        return 'ya_existe'

    if fila.get('propio') and fila['clase'] == 'traspaso':
        from datetime import timedelta
        hay_par = MovimientoFinanciero.objects.filter(
            clase='traspaso', sentido='entra', cuenta__clave=cuenta_clave,
            monto=monto, fecha__range=(fecha - timedelta(days=2),
                                       fecha + timedelta(days=2))).exists()
        return 'ya_existe' if hay_par else 'revisar'

    if cuenta_clave == 'scotiabank' and fila['clase'] == 'gasto':
        if MovimientoFinanciero.objects.filter(
                referencia__startswith='hist:', cuenta__clave=cuenta_clave,
                monto=monto, fecha__year=fecha.year,
                fecha__month=fecha.month).exists():
            return 'en_historico'
    else:
        if MovimientoFinanciero.objects.filter(
                referencia__startswith='hist:', cuenta__clave=cuenta_clave,
                fecha=fecha, monto=monto).exists():
            return 'en_historico'

    return 'nuevo'


# ── F5: comisiones de SumUp por la API ───────────────────────────────────────
# Estructura real verificada 2026-08-08 (sonda): /v0.1/me/financials/payouts
# devuelve un item POR TRANSACCIÓN liquidada: {"amount": neto, "fee": comisión,
# "date": "AAAA-MM-DD", "id": único, "type": "PAYOUT", "status": "SUCCESSFUL"}.
# El neto ya entra a BancoEstado vía cartola (ingreso liquidacion_sumup), así
# que acá solo se registra la COMISIÓN — en la cuenta puente "SumUp (en
# tránsito)", que no está en el flujo de caja (no mueve saldos) pero sí suma
# al gasto del mes en el tablero. Mismo patrón que las comisiones MP.


def registrar_payouts_sumup(items):
    """Núcleo puro-DB: convierte items de payouts en gastos de comisión.

    Idempotente por referencia sumup:fee:<id>; corte julio; solo PAYOUT
    SUCCESSFUL con fee > 0. Devuelve (creados, saltados).
    """
    from .models import (CategoriaFinanciera, CuentaFinanciera,
                         MovimientoFinanciero)

    try:
        cuenta = CuentaFinanciera.objects.get(clave='sumup_transito')
        cat = CategoriaFinanciera.objects.get(clave='comisiones')
    except (CuentaFinanciera.DoesNotExist, CategoriaFinanciera.DoesNotExist):
        logger.warning('finanzas sin sembrar (sumup_transito): comisiones '
                       'SumUp no registradas')
        return 0, 0

    creados = saltados = 0
    for p in items:
        try:
            if (p.get('type') != 'PAYOUT'
                    or p.get('status') != 'SUCCESSFUL'):
                saltados += 1
                continue
            fee = int(round(float(p.get('fee') or 0)))
            pid = p.get('id')
            fecha = date.fromisoformat(str(p.get('date') or ''))
            if not pid or fee <= 0 or fecha < COBERTURA_GASTOS_DESDE:
                saltados += 1
                continue
            ref = f'sumup:fee:{pid}'
            if MovimientoFinanciero.objects.filter(referencia=ref).exists():
                saltados += 1
                continue
            MovimientoFinanciero.objects.create(
                fecha=fecha, cuenta=cuenta, clase='gasto', sentido='sale',
                monto=fee, categoria=cat, fuente='api', referencia=ref,
                descripcion=(f"Comisión SumUp venta {p.get('transaction_code') or pid} "
                             f"(neto ${int(float(p.get('amount') or 0)):,})"
                             .replace(',', '.'))[:255])
            creados += 1
        except Exception:
            logger.exception('payout SumUp %s no registrado', p.get('id'))
    return creados, saltados


def traer_comisiones_sumup(dias=7):
    """Capa fina: consulta payouts a la API de SumUp y registra comisiones.

    Devuelve (creados, total_api). Lanza RuntimeError si no hay clave —
    el que llama decide si eso es un salto limpio o un error.
    """
    import os

    import requests

    clave = os.environ.get('SUMUP_API_KEY')
    if not clave:
        raise RuntimeError('SUMUP_API_KEY no configurada')

    from datetime import timedelta
    desde = (date.today() - timedelta(days=dias)).isoformat()
    r = requests.get(
        'https://api.sumup.com/v0.1/me/financials/payouts',
        headers={'Authorization': f'Bearer {clave}'},
        params={'start_date': desde, 'end_date': date.today().isoformat()},
        timeout=30,
    )
    r.raise_for_status()
    datos = r.json()
    items = datos if isinstance(datos, list) else (datos.get('items') or [])
    creados, _ = registrar_payouts_sumup(items)
    if creados:
        logger.info('finanzas: %s comisiones SumUp registradas', creados)
    return creados, len(items)
