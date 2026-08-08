# -*- coding: utf-8 -*-
"""Conciliador F1: fetch de pagos desde la API de Mercado Pago + matcher + aplicar.

Flujo (supervisado): botón admin "Traer pagos de MP" → `traer_pagos_mp()` guarda
los pagos nuevos como MovimientoMP (idempotente por mp_payment_id) y les corre
`matchear_movimiento()` → queda una sugerencia; Deborah confirma con 1 clic
(`aplicar_movimiento()`, que reusa `registrar_pago` + ReconciliacionLog).

Reglas de match (en orden):
  1. external_reference = id de reserva (links generados por reserva) → directo.
  2. UNA sola reserva pendiente/parcial con saldo_pendiente == monto.
  3. UNA sola con total == monto (pago completo de reserva sin abonos).
  4. UNA sola con total/2 == monto (abono 50%, común en Aremko).
  5. Si hay varias candidatas pero la glosa contiene el nombre de UN solo
     cliente candidato → esa.
  De lo contrario → estado 'revisar' (cola de Deborah).
"""
import logging
import re
import unicodedata
from datetime import timedelta
from decimal import Decimal

import requests
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

logger = logging.getLogger(__name__)

VENTANA_RESERVA_DIAS = 60  # candidatas: reservas creadas hasta N días antes del pago


def _sin_tildes(texto):
    return ''.join(c for c in unicodedata.normalize('NFD', texto or '')
                   if unicodedata.category(c) != 'Mn').lower()


def ids_en_glosa(glosa):
    """Números de 2-6 dígitos mencionados en la glosa (posibles IDs de reserva).

    Función pura. Los clientes a veces escriben "Reserva 6195" o "R 6203" al
    transferir (visto en datos reales del sondeo 2026-07-06). Los falsos
    positivos (fechas, referencias largas) se filtran después contra las
    reservas PENDIENTES de la ventana — un número suelto solo matchea si
    existe esa reserva con saldo.
    """
    return [int(n) for n in re.findall(r'\d{2,6}', glosa or '')]


def nombre_en_glosa(nombre_cliente, glosa):
    """True si algún token (>3 letras) del nombre del cliente aparece en la glosa.

    Función pura (testeable sin BD). Compara sin tildes ni mayúsculas:
    'Héctor Azúcar' matchea la glosa "Reserva hector azucar". (El "H?ctor" que
    se vio en el sondeo era el encoding de la TERMINAL del Shell, no del dato.)
    """
    glosa_norm = _sin_tildes(glosa)
    if not glosa_norm:
        return False
    tokens = [t for t in _sin_tildes(nombre_cliente).split() if len(t) > 3]
    return any(t in glosa_norm for t in tokens)


def id_cuenta_mp(token):
    """Id de usuario de la cuenta dueña del token (Aremko).

    Hace falta para distinguir lo que Aremko COBRA de lo que Aremko PAGA:
    `/v1/payments/search` devuelve las dos cosas y no acepta filtrarlo por
    parametro, asi que la separacion se hace comparando `collector_id`.

    Se consulta a la API en vez de guardarlo en settings a proposito: una
    constante mal copiada dejaria el filtro descartando TODO en silencio.
    """
    r = requests.get(
        'https://api.mercadopago.com/users/me',
        headers={'Authorization': f'Bearer {token}'},
        timeout=30,
    )
    r.raise_for_status()
    mi_id = r.json().get('id')
    if not mi_id:
        raise RuntimeError('Mercado Pago no devolvio el id de la cuenta en /users/me')
    return str(mi_id)


def es_cobro_nuestro(pago, mi_id):
    """True si en este pago Aremko es quien COBRA (no quien paga).

    Sin este filtro entran a la cola de Deborah las compras que Aremko hace por
    Mercado Pago (Mercado Libre, retail), que no tienen reserva a la cual
    aplicarse. Detectado 2026-08-08: eran ~40% de la cola.
    """
    cobrador = pago.get('collector_id')
    if cobrador is None:
        cobrador = (pago.get('collector') or {}).get('id')
    return cobrador is not None and str(cobrador) == str(mi_id)


def traer_pagos_mp(dias=14):
    """Consulta /v1/payments/search (approved) y guarda los nuevos MovimientoMP.

    Solo guarda los pagos donde Aremko es el COBRADOR. Idempotente: los
    mp_payment_id ya vistos se saltan. Devuelve (nuevos, total_api).
    """
    from .models import MovimientoMP

    token = getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', None)
    if not token:
        raise RuntimeError('MERCADOPAGO_ACCESS_TOKEN no configurado')

    # Si esto falla se corta aca a proposito. Seguir sin el id significaria
    # volver a mezclar compras con cobros, que es el bug que esto arregla.
    mi_id = id_cuenta_mp(token)

    desde = timezone.now() - timedelta(days=dias)
    resultados, offset = [], 0
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
        resultados.extend(page)
        total_api = data.get('paging', {}).get('total', 0)
        offset += len(page)
        if not page or offset >= total_api or offset >= 500:
            break

    # OJO: `resultados` se reduce aca, pero el segundo valor que devuelve esta
    # funcion es el total que trajo la API — no el filtrado. Si se cambia, el
    # boton del admin pasa a mentir sobre cuanto reviso.
    total_traidos = len(resultados)
    compras = [p for p in resultados if not es_cobro_nuestro(p, mi_id)]
    resultados = [p for p in resultados if es_cobro_nuestro(p, mi_id)]
    if compras:
        logger.info(
            'MP: descartados %s pagos donde Aremko no es el cobrador (de %s)',
            len(compras), total_traidos,
        )
        # Un fetch, dos consumidores (P-22 F2-B): lo que para la cola de
        # Deborah es ruido (Aremko pagador) para finanzas es exactamente el
        # gasto pagado via MP. Best-effort: un fallo alla no rompe esto.
        try:
            from finanzas.services import registrar_compras_mp
            registrar_compras_mp(compras)
        except Exception:
            logger.exception('compras MP → finanzas fallaron (la conciliacion sigue)')

    vistos = set(MovimientoMP.objects.filter(
        mp_payment_id__in=[str(p.get('id')) for p in resultados]
    ).values_list('mp_payment_id', flat=True))

    nuevos = []
    for p in resultados:
        pid = str(p.get('id'))
        if pid in vistos:
            continue
        monto = Decimal(str(int(p.get('transaction_amount') or 0)))
        if monto <= 0:
            continue
        fecha = parse_datetime(p.get('date_approved') or p.get('date_created') or '') or timezone.now()
        td = p.get('transaction_details') or {}
        payer = p.get('payer') or {}
        mov = MovimientoMP(
            mp_payment_id=pid,
            fecha=fecha,
            monto=monto,
            tipo=f"{p.get('operation_type', '')}/{p.get('payment_type_id', '')}",
            glosa=(p.get('description') or '')[:255],
            transaction_id=(td.get('transaction_id') or '')[:80],
            payer_email=(payer.get('email') or '')[:254],
            external_reference=(p.get('external_reference') or '')[:64],
            # raw acotado: lo necesario para auditar sin guardar el JSON gigante
            raw={k: p.get(k) for k in (
                'id', 'status', 'operation_type', 'payment_type_id',
                'transaction_amount', 'date_approved', 'description',
                'external_reference') if p.get(k) is not None},
        )
        matchear_movimiento(mov)  # setea estado/sugerencia/motivo (no guarda)
        mov.save()
        nuevos.append(mov)

    return nuevos, total_traidos


def matchear_movimiento(mov):
    """Calcula la sugerencia para un MovimientoMP (muta el objeto, NO guarda)."""
    from ventas.models import VentaReserva

    # Regla 1: external_reference = id de reserva → match directo.
    # Si la reserva ya quedó sin saldo, el webhook de MP Link ya registró este
    # pago → auto-ignorar (evita ruido en la cola). Si aún tiene saldo, el
    # webhook falló o va atrasado → el Conciliador actúa de RESPALDO (sugerido).
    if mov.external_reference.strip().isdigit():
        reserva = VentaReserva.objects.filter(id=int(mov.external_reference)).first()
        if reserva:
            mov.sugerencia = reserva
            if Decimal(reserva.saldo_pendiente or 0) <= 0:
                mov.sugerencia_motivo = 'pago por link — ya registrado por el webhook'
                mov.estado = 'ignorado'
            else:
                mov.sugerencia_motivo = 'external_reference del link de pago (respaldo del webhook)'
                mov.estado = 'sugerido'
            return mov

    desde = mov.fecha - timedelta(days=VENTANA_RESERVA_DIAS)
    candidatas_base = (VentaReserva.objects
                       .filter(estado_pago__in=('pendiente', 'parcial'),
                               fecha_creacion__gte=desde,
                               fecha_creacion__lte=mov.fecha + timedelta(days=1))
                       .select_related('cliente'))

    # Regla 1.5: número de reserva escrito en la glosa ("Reserva 6195", "R 6203")
    # — señal más fuerte que el monto; solo cuenta si esa reserva está PENDIENTE
    # en la ventana (así "43" o un año en la glosa no matchean reservas viejas).
    ids_glosa = set(ids_en_glosa(mov.glosa))
    if ids_glosa:
        por_id = [r for r in candidatas_base if r.id in ids_glosa]
        if len(por_id) == 1:
            mov.sugerencia = por_id[0]
            mov.sugerencia_motivo = 'número de reserva en la glosa'
            mov.estado = 'sugerido'
            return mov

    por_regla = [
        ('saldo exacto', [r for r in candidatas_base if Decimal(r.saldo_pendiente or 0) == mov.monto]),
        ('total exacto', [r for r in candidatas_base if Decimal(r.total or 0) == mov.monto and r.estado_pago == 'pendiente']),
        ('abono 50% del total', [r for r in candidatas_base if Decimal(r.total or 0) == mov.monto * 2 and r.estado_pago == 'pendiente']),
    ]

    for motivo, candidatas in por_regla:
        if len(candidatas) == 1:
            mov.sugerencia = candidatas[0]
            mov.sugerencia_motivo = motivo
            mov.estado = 'sugerido'
            return mov
        if len(candidatas) > 1:
            # Desambiguar por nombre del cliente en la glosa
            con_nombre = [r for r in candidatas
                          if r.cliente and nombre_en_glosa(r.cliente.nombre, mov.glosa)]
            if len(con_nombre) == 1:
                mov.sugerencia = con_nombre[0]
                mov.sugerencia_motivo = f'{motivo} + nombre en la glosa'
                mov.estado = 'sugerido'
                return mov
            mov.sugerencia_motivo = f'{len(candidatas)} reservas con {motivo} — elegir a mano'
            mov.estado = 'revisar'
            return mov

    mov.sugerencia_motivo = 'sin reserva pendiente con monto compatible'
    mov.estado = 'revisar'
    return mov


def aplicar_movimiento(mov, reserva, actor='admin'):
    """Aplica un MovimientoMP a una reserva: Pago + saldo + auditoría. Idempotente.

    Reusa el mecanismo limpio (`registrar_pago`) y deja ReconciliacionLog con
    referencia = transaction_id (o mp_<id>) — el mismo movimiento no se aplica 2 veces.
    """
    from .models import ReconciliacionLog

    referencia = mov.transaction_id or f'mp_{mov.mp_payment_id}'
    if ReconciliacionLog.objects.filter(referencia=referencia).exists():
        return False, f'Ya aplicado antes (referencia {referencia})'

    # Candado anti-duplicado: si la reserva ya no tiene saldo, este pago
    # probablemente ya fue registrado A MANO (caso típico de la primera tanda
    # histórica) — o alguien aplicó otro movimiento a la misma reserva recién.
    reserva.refresh_from_db()
    saldo = Decimal(reserva.saldo_pendiente or 0)
    if saldo <= 0:
        return False, (f'Reserva #{reserva.id} ya no tiene saldo pendiente — '
                       f'este pago probablemente ya está registrado. Usa "Ignorar".')

    metodo = 'transferencia' if 'bank_transfer' in mov.tipo else 'mercadopago'
    with transaction.atomic():
        reserva.registrar_pago(mov.monto, metodo)
        pago = reserva.pagos.order_by('-id').first()
        ReconciliacionLog.objects.create(
            referencia=referencia,
            reserva=reserva,
            pago=pago,
            monto=mov.monto,
            metodo_pago=metodo,
            origen='mp_api',
            actor=actor,
            fecha_movimiento=mov.fecha,
            payload=mov.raw,
            notas=f'Conciliador F1 · {mov.sugerencia_motivo} · glosa: {mov.glosa}'[:500],
        )
        mov.estado = 'aplicado'
        mov.reserva_aplicada = reserva
        mov.save(update_fields=['estado', 'reserva_aplicada', 'actualizado_en'])

    reserva.refresh_from_db()
    return True, f'Aplicado a reserva #{reserva.id} → estado {reserva.estado_pago}, saldo ${int(reserva.saldo_pendiente):,}'
