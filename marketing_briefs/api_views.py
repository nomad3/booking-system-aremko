"""API de publicaciones planificadas para aremko-cli (la cola de Angélica).

Auth: header X-API-KEY == settings.AUTOMATION_API_KEY (la key vive
server-side en el backend Go de aremko-cli, nunca en el navegador).
"""

import json
import logging
from datetime import date, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PublicacionPlanificada

logger = logging.getLogger(__name__)

ESTADOS_VALIDOS = {choice[0] for choice in PublicacionPlanificada.ESTADO_CHOICES}


def _api_key_ok(request) -> bool:
    expected = getattr(settings, 'AUTOMATION_API_KEY', '') or ''
    provided = request.headers.get('X-API-KEY', '')
    return bool(expected) and provided == expected


def _serialize(p: PublicacionPlanificada) -> dict:
    return {
        'id': p.id,
        'semana_inicio': p.semana_inicio.isoformat(),
        'dia': p.dia.isoformat(),
        'canal': p.canal,
        'tipo': p.tipo,
        'pieza_key': p.pieza_key,
        'titulo': p.titulo,
        'copy_json': p.copy_json,
        'responsable': p.responsable,
        'tiempo_estimado': p.tiempo_estimado,
        'estado': p.estado,
        'material_urls': p.material_urls,
        'notas_revision': p.notas_revision,
        'published_url': p.published_url,
        'metricas': p.metricas,
        'notas': p.notas,
        'updated_at': p.updated_at.isoformat(),
    }


@csrf_exempt
@require_http_methods(['GET'])
def publicaciones_semana(request):
    """Lista las publicaciones de una semana (default: la semana en curso).

    Query params:
        semana: YYYY-MM-DD (cualquier día; se normaliza al lunes). Opcional.
    """
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    try:
        semana_param = (request.GET.get('semana') or '').strip()
        if semana_param:
            base = date.fromisoformat(semana_param)
        else:
            base = date.today()
        lunes = base - timedelta(days=base.weekday())

        qs = PublicacionPlanificada.objects.filter(semana_inicio=lunes).order_by('dia', 'id')
        items = [_serialize(p) for p in qs]
        return JsonResponse({
            'semana_inicio': lunes.isoformat(),
            'total': len(items),
            'publicaciones': items,
        })
    except ValueError:
        return JsonResponse({'error': 'Parámetro semana inválido (usar YYYY-MM-DD)'}, status=400)
    except Exception as exc:  # noqa: BLE001
        logger.error(f'publicaciones_semana: {exc}', exc_info=True)
        return JsonResponse({'error': str(exc)}, status=500)


@csrf_exempt
@require_http_methods(['POST'])
def publicacion_actualizar(request, pub_id: int):
    """Actualiza estado / notas / published_url de una publicación.

    Body JSON: {"estado": "...", "published_url": "...", "notas": "..."}
    (todos opcionales; solo se tocan los campos presentes).
    """
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return JsonResponse({'error': f'Publicación {pub_id} no existe'}, status=404)

    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Body no es JSON válido'}, status=400)

    cambios = []
    estado = payload.get('estado')
    if estado is not None:
        if estado not in ESTADOS_VALIDOS:
            return JsonResponse(
                {'error': f'Estado inválido. Válidos: {sorted(ESTADOS_VALIDOS)}'}, status=400,
            )
        pub.estado = estado
        cambios.append('estado')

    if 'published_url' in payload:
        pub.published_url = (payload.get('published_url') or '')[:500]
        cambios.append('published_url')

    if 'notas' in payload:
        pub.notas = payload.get('notas') or ''
        cambios.append('notas')

    if not cambios:
        return JsonResponse({'error': 'Nada que actualizar (enviar estado, published_url o notas)'}, status=400)

    pub.save(update_fields=cambios + ['updated_at'])
    logger.info(f'publicacion_actualizar: #{pub_id} campos {cambios}')
    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})
