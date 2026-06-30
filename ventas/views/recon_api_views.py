"""API de conciliación bancaria (AP-001 · Tier-2 "Adapter Spec") para AgentProvision.

Implementa el contrato del SISTEMA DE REGISTRO que consume el agente Conciliador:
- GET  reservas-pendientes → las "invoices" a conciliar (reservas con saldo).
- POST aplicar-pago        → escribe el pago conciliado (PASO 2, pendiente; necesita auditoría).

Auth: AUTOMATION_API_KEY (header `X-API-KEY`), mismo esquema que el resto de la API aremko-cli.
Read-only por ahora (sin escritura, sin modelos nuevos → sin migración). Ver
docs/BRIEF_AP-001_conexion_conciliacion.md y docs/HANDOFFS_AGENTPROVISION.md.
"""
import json
import logging

from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ventas.views.bandeja_whatsapp_views import _require_api_key

logger = logging.getLogger(__name__)


@csrf_exempt
@require_http_methods(['GET'])
def recon_reservas_pendientes(request):
    """GET /ventas/api/aremko-cli/recon/reservas-pendientes/

    Reservas con saldo (`estado_pago` en `pendiente`|`parcial`) = las "invoices" a conciliar.
    Filtros opcionales:
      - ?desde=YYYY-MM-DD & ?hasta=YYYY-MM-DD  (sobre fecha_creacion)
      - ?q=<nombre|rut|email|teléfono del cliente>
      - ?limit=N  (máx 500, default 100)
    Read-only. Auth: AUTOMATION_API_KEY (X-API-KEY).
    """
    auth = _require_api_key(request)
    if auth:
        return auth

    from ventas.models import VentaReserva

    qs = (VentaReserva.objects
          .filter(estado_pago__in=['pendiente', 'parcial'])
          .select_related('cliente'))

    desde = (request.GET.get('desde') or '').strip()
    hasta = (request.GET.get('hasta') or '').strip()
    if desde:
        qs = qs.filter(fecha_creacion__date__gte=desde)
    if hasta:
        qs = qs.filter(fecha_creacion__date__lte=hasta)

    q = (request.GET.get('q') or '').strip()
    if q:
        qs = qs.filter(
            Q(cliente__nombre__icontains=q)
            | Q(cliente__documento_identidad__icontains=q)
            | Q(cliente__email__icontains=q)
            | Q(cliente__telefono__icontains=q)
        )

    try:
        limit = min(int(request.GET.get('limit', 100)), 500)
    except (TypeError, ValueError):
        limit = 100

    reservas = []
    for r in qs.order_by('-fecha_creacion')[:limit]:
        c = r.cliente
        reservas.append({
            'reserva_id': r.id,
            'numero': f'RES-{r.id}',
            'cliente': ({
                'id': c.id,
                'nombre': c.nombre,
                'rut': c.documento_identidad,
                'email': c.email,
                'telefono': c.telefono,
            } if c else None),
            'total': int(r.total or 0),
            'pagado': int(r.pagado or 0),
            'saldo_pendiente': int(r.saldo_pendiente or 0),
            'estado_pago': r.estado_pago,
            'fecha_reserva': r.fecha_reserva.isoformat() if r.fecha_reserva else None,
            'fecha_creacion': r.fecha_creacion.isoformat() if r.fecha_creacion else None,
        })

    return JsonResponse({'count': len(reservas), 'reservas': reservas})


def _parse_fecha_movimiento(valor):
    """Acepta ISO datetime o date (YYYY-MM-DD). Devuelve aware datetime o None."""
    if not valor:
        return None
    dt = parse_datetime(valor)
    if dt is not None:
        return timezone.make_aware(dt) if timezone.is_naive(dt) else dt
    d = parse_date(valor)
    if d is not None:
        from datetime import datetime, time
        return timezone.make_aware(datetime.combine(d, time.min))
    return None


def _respuesta_reconciliacion(log, reserva, ya_aplicado):
    """Cuerpo JSON común para aplicar-pago (nuevo o idempotente)."""
    return {
        'ok': True,
        'ya_aplicado': ya_aplicado,
        'reconciliacion_id': log.id if log else None,
        'reserva_id': (log.reserva_id if log else (reserva.id if reserva else None)),
        'pago_id': log.pago_id if log else None,
        'monto_aplicado': int(log.monto) if (log and log.monto is not None) else None,
        'estado_pago': reserva.estado_pago if reserva else None,
        'saldo_pendiente': int(reserva.saldo_pendiente or 0) if reserva else None,
    }


@csrf_exempt
@require_http_methods(['POST'])
def recon_aplicar_pago(request):
    """POST /ventas/api/aremko-cli/recon/aplicar-pago/

    Aplica un pago conciliado a una reserva (lo decide AgentProvision; Django solo registra).
    Body JSON:
      - reserva_id   (int, requerido)
      - monto        (número CLP, requerido, > 0)
      - referencia   (str, requerido) → ID ÚNICO del movimiento; clave de idempotencia
      - metodo_pago  (str, opcional, default 'transferencia'; debe ser un METODOS_PAGO válido)
      - origen       (str, opcional, default 'gmail')
      - actor        (str, opcional, default 'agentprovision')
      - fecha_movimiento (str ISO/fecha, opcional)
      - notas        (str, opcional)
      - payload      (objeto, opcional; si falta se guarda el body completo) → auditoría

    Idempotente por `referencia`: reenviar el mismo movimiento devuelve el resultado previo
    SIN crear un segundo pago. Reusa el mecanismo limpio del modelo (crea Pago + recalcula
    saldo vía calcular_total → actualizar_saldo; igual que VentaReserva.registrar_pago).
    Read-after-write auditado en conciliacion.ReconciliacionLog. Auth: AUTOMATION_API_KEY.
    """
    auth = _require_api_key(request)
    if auth:
        return auth

    from ventas.models import Pago, VentaReserva
    from conciliacion.models import ReconciliacionLog

    try:
        data = json.loads(request.body or '{}')
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'JSON inválido'}, status=400)
    if not isinstance(data, dict):
        return JsonResponse({'ok': False, 'error': 'El body debe ser un objeto JSON'}, status=400)

    referencia = str(data.get('referencia') or '').strip()
    reserva_id = data.get('reserva_id')
    metodo_pago = str(data.get('metodo_pago') or 'transferencia').strip()
    origen = str(data.get('origen') or 'gmail').strip()
    actor = str(data.get('actor') or 'agentprovision').strip()
    notas = str(data.get('notas') or '').strip()
    payload = data.get('payload')
    if not isinstance(payload, (dict, list)):
        payload = data  # guarda el body completo como auditoría

    # --- Validaciones ---
    if not referencia:
        return JsonResponse({'ok': False, 'error': 'referencia es requerida (idempotencia)'}, status=400)
    if not reserva_id:
        return JsonResponse({'ok': False, 'error': 'reserva_id es requerido'}, status=400)
    try:
        monto = int(round(float(data.get('monto'))))
    except (TypeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'monto inválido'}, status=400)
    if monto <= 0:
        return JsonResponse({'ok': False, 'error': 'monto debe ser > 0'}, status=400)

    metodos_validos = {m[0] for m in Pago.METODOS_PAGO}
    if metodo_pago not in metodos_validos:
        return JsonResponse({
            'ok': False,
            'error': f'metodo_pago inválido: {metodo_pago}',
            'validos': sorted(metodos_validos),
        }, status=400)

    # --- Idempotencia: ¿ya se aplicó este movimiento? ---
    existente = (ReconciliacionLog.objects
                 .filter(referencia=referencia)
                 .select_related('reserva').first())
    if existente:
        return JsonResponse(_respuesta_reconciliacion(existente, existente.reserva, ya_aplicado=True))

    try:
        reserva = VentaReserva.objects.get(id=reserva_id)
    except VentaReserva.DoesNotExist:
        return JsonResponse({'ok': False, 'error': 'Reserva no encontrada'}, status=404)

    fecha_mov = _parse_fecha_movimiento(data.get('fecha_movimiento'))

    try:
        with transaction.atomic():
            # Mecanismo limpio (igual que VentaReserva.registrar_pago, models.py:1228),
            # pero capturando el Pago: crear Pago + recalcular saldo/estado_pago.
            pago = Pago.objects.create(venta_reserva=reserva, monto=monto, metodo_pago=metodo_pago)
            reserva.calcular_total()  # → actualizar_saldo() recalcula pagado/saldo/estado_pago
            log = ReconciliacionLog.objects.create(
                referencia=referencia,
                reserva=reserva,
                pago=pago,
                monto=monto,
                metodo_pago=metodo_pago,
                origen=origen,
                actor=actor,
                fecha_movimiento=fecha_mov,
                payload=payload,
                estado='aplicado',
                notas=notas,
            )
    except IntegrityError:
        # Carrera: otra request aplicó la misma referencia entremedio → idempotente.
        existente = (ReconciliacionLog.objects
                     .filter(referencia=referencia)
                     .select_related('reserva').first())
        if existente:
            return JsonResponse(_respuesta_reconciliacion(existente, existente.reserva, ya_aplicado=True))
        return JsonResponse({'ok': False, 'error': 'Conflicto de idempotencia'}, status=409)
    except Exception as e:  # noqa: BLE001
        logger.error('recon_aplicar_pago error (reserva %s, ref %s): %s', reserva_id, referencia, e)
        return JsonResponse({'ok': False, 'error': 'Error aplicando el pago'}, status=500)

    reserva.refresh_from_db()
    logger.info('Conciliación aplicada: ref=%s reserva=%s monto=%s → estado=%s',
                referencia, reserva.id, monto, reserva.estado_pago)
    return JsonResponse(_respuesta_reconciliacion(log, reserva, ya_aplicado=False))
