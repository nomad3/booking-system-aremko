# -*- coding: utf-8 -*-
"""API de la cola de notificaciones a staff (Luna Interna · Fase 2).

aremko-cli (que tiene el token de WhatsApp) DRENA esta cola:
  - GET  /api/staff/notificaciones?limit=N   → notificaciones pendientes a enviar
  - POST /api/staff/notificaciones/marcar    → marca {ids} como enviada|fallida

Auth: header X-API-Key (settings.LUNA_API_KEY), igual que el resto de la API de Luna.
"""
import json

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt


def _check_key(request):
    expected = getattr(settings, 'LUNA_API_KEY', None)
    provided = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
    if not expected or not provided or provided != expected:
        return JsonResponse({'error': 'No autorizado. Se requiere header X-API-Key válido.'}, status=401)
    return None


@csrf_exempt
def notificaciones_pendientes(request):
    """Lista las notificaciones pendientes para que aremko-cli las envíe."""
    err = _check_key(request)
    if err:
        return err
    from .models import NotificacionStaff
    try:
        limit = min(int(request.GET.get('limit', 50)), 200)
    except (ValueError, TypeError):
        limit = 50
    qs = NotificacionStaff.objects.filter(estado='pendiente').order_by('creada')[:limit]
    return JsonResponse({
        'count': len(qs),
        'notificaciones': [{
            'id': n.id,
            'telefono': n.telefono,
            'texto': n.texto,
            'dedup_key': n.dedup_key,
            'origen': n.origen,
            'creada': n.creada.isoformat(),
        } for n in qs],
    })


@csrf_exempt
def marcar_notificaciones(request):
    """Marca notificaciones como enviada|fallida|descartada.

    Body JSON: {"ids": [1,2], "estado": "enviada"}  (o "fallida" con "error" opcional)
    """
    err = _check_key(request)
    if err:
        return err
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        data = json.loads(request.body or b'{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    ids = data.get('ids') or []
    estado = (data.get('estado') or 'enviada').strip()
    if estado not in ('enviada', 'fallida', 'descartada'):
        return JsonResponse({'error': 'estado inválido'}, status=400)
    if not isinstance(ids, list) or not ids:
        return JsonResponse({'error': 'ids (lista) requerido'}, status=400)

    from .models import NotificacionStaff
    from django.db.models import F
    qs = NotificacionStaff.objects.filter(id__in=ids)
    campos = {'estado': estado, 'intentos': F('intentos') + 1}
    if estado == 'enviada':
        campos['enviada_at'] = timezone.now()
    if estado == 'fallida' and data.get('error'):
        campos['error'] = str(data.get('error'))[:500]
    actualizadas = qs.update(**campos)
    return JsonResponse({'ok': True, 'actualizadas': actualizadas})
