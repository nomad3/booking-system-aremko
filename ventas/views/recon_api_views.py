"""API de conciliación bancaria (AP-001 · Tier-2 "Adapter Spec") para AgentProvision.

Implementa el contrato del SISTEMA DE REGISTRO que consume el agente Conciliador:
- GET  reservas-pendientes → las "invoices" a conciliar (reservas con saldo).
- POST aplicar-pago        → escribe el pago conciliado (PASO 2, pendiente; necesita auditoría).

Auth: AUTOMATION_API_KEY (header `X-API-KEY`), mismo esquema que el resto de la API aremko-cli.
Read-only por ahora (sin escritura, sin modelos nuevos → sin migración). Ver
docs/BRIEF_AP-001_conexion_conciliacion.md y docs/HANDOFFS_AGENTPROVISION.md.
"""
import logging

from django.db.models import Q
from django.http import JsonResponse
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
