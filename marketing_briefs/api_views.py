"""API de publicaciones planificadas para aremko-cli (la cola de Angélica).

Auth: header X-API-KEY == settings.AUTOMATION_API_KEY (la key vive
server-side en el backend Go de aremko-cli, nunca en el navegador).
"""

import json
import logging
import os
import uuid
from datetime import date, timedelta

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import PublicacionPlanificada

logger = logging.getLogger(__name__)

# Extensiones de imagen aceptadas en la Fase 2 (fotos/carruseles/historias).
_EXT_IMAGEN = {'.jpg', '.jpeg', '.png', '.webp', '.heic', '.heif'}
_MAX_BYTES = 16 * 1024 * 1024  # 16 MB por archivo, mismo tope que la bandeja.

# Video (H-065 / H-066 F2): micro-clips por segmento de reel o el reel completo.
# El tope queda bajo el body máximo del proxy Go de aremko-cli (110 MB); el
# contrato recomienda <40 MB (clips H.264 reales pesan 5-20 MB).
_EXT_VIDEO = {'.mp4', '.mov'}
_MAX_BYTES_VIDEO = 100 * 1024 * 1024

ESTADOS_VALIDOS = {choice[0] for choice in PublicacionPlanificada.ESTADO_CHOICES}


def _ratio_label(w: int, h: int) -> tuple:
    """Devuelve (ratio_str, orientacion) a partir del ancho×alto REAL de la
    foto. Esto hace que el chequeo de formato (historia 9:16, feed 4:5/1:1)
    sea exacto y no dependa de que el modelo lo estime a ojo."""
    if not w or not h:
        return '', ''
    r = w / h
    if abs(r - 9 / 16) < 0.06:      # 0.5625
        return '9:16', 'vertical'
    if abs(r - 4 / 5) < 0.06:       # 0.80
        return '4:5', 'vertical'
    if abs(r - 1) < 0.06:
        return '1:1', 'cuadrada'
    if abs(r - 16 / 9) < 0.12:      # 1.78
        return '16:9', 'horizontal'
    if r < 0.95:
        return f'{r:.2f}', 'vertical'
    if r > 1.05:
        return f'{r:.2f}', 'horizontal'
    return f'{r:.2f}', 'cuadrada'


def _medir_imagen(f) -> dict:
    """Lee ancho×alto de un archivo subido sin consumir el stream (best-effort).
    HEIC/HEIF u otros formatos que Pillow no abra devuelven dict vacío — el
    flujo sigue igual, solo se pierde el chequeo de proporción de esa foto."""
    try:
        from PIL import Image
        f.seek(0)
        with Image.open(f) as img:
            w, h = img.size
        ratio, orientacion = _ratio_label(w, h)
        return {'width': int(w), 'height': int(h), 'ratio': ratio, 'orientacion': orientacion}
    except Exception as exc:  # noqa: BLE001 — nunca bloquea la subida
        logger.info(f'_medir_imagen: no se pudo medir ({exc})')
        return {}
    finally:
        try:
            f.seek(0)
        except Exception:  # noqa: BLE001
            pass


def _subir_video_cloudinary(f, nombre: str) -> dict:
    """Sube un video a Cloudinary (chunked, resource_type video) y devuelve el
    item de material_meta: {url, tipo:'video', width, height, ratio, orientacion,
    duration, bytes, format}. Es el equivalente video de `_medir_imagen`: la
    metadata (duración, dimensiones) viene en la respuesta del upload, sin
    descargar ni procesar nada. Si un campo de metadata falta, el item sale
    igual con lo que haya. Lanza excepción solo si la subida misma falla."""
    import cloudinary
    import cloudinary.uploader

    # cloudinary_storage suele dejar el SDK configurado; si no, mismas env vars
    # que usa settings para armar CLOUDINARY_STORAGE.
    if not cloudinary.config().cloud_name:
        cloudinary.config(
            cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
            api_key=os.getenv('CLOUDINARY_API_KEY'),
            api_secret=os.getenv('CLOUDINARY_API_SECRET'),
            secure=True,
        )

    try:
        f.seek(0)
    except Exception:  # noqa: BLE001
        pass
    resp = cloudinary.uploader.upload_large(
        f,
        resource_type='video',
        public_id=nombre.rsplit('.', 1)[0],  # Cloudinary agrega la extensión según el format
        chunk_size=20 * 1024 * 1024,
    )

    item = {'url': resp.get('secure_url') or resp.get('url') or '', 'tipo': 'video'}
    w, h = resp.get('width'), resp.get('height')
    if w and h:
        ratio, orientacion = _ratio_label(w, h)
        item.update({'width': int(w), 'height': int(h), 'ratio': ratio, 'orientacion': orientacion})
    if resp.get('duration') is not None:
        try:
            item['duration'] = round(float(resp['duration']), 1)
        except (TypeError, ValueError):
            pass
    if resp.get('bytes'):
        item['bytes'] = int(resp['bytes'])
    if resp.get('format'):
        item['format'] = resp['format']
    if not item['url']:
        raise ValueError('Cloudinary no devolvió URL del video subido')
    return item


def _api_key_ok(request) -> bool:
    expected = getattr(settings, 'AUTOMATION_API_KEY', '') or ''
    provided = request.headers.get('X-API-KEY', '')
    return bool(expected) and provided == expected


def _serialize(p: PublicacionPlanificada) -> dict:
    return {
        'id': p.id,
        'semana_inicio': p.semana_inicio.isoformat(),
        'dia': p.dia.isoformat(),
        'hora_sugerida': p.hora_sugerida,
        'canal': p.canal,
        'tipo': p.tipo,
        'pieza_key': p.pieza_key,
        'titulo': p.titulo,
        'copy_json': p.copy_json,
        'responsable': p.responsable,
        'tiempo_estimado': p.tiempo_estimado,
        'estado': p.estado,
        'material_urls': p.material_urls,
        'material_meta': p.material_meta,
        'segmentos': p.segmentos,
        'revision_veredicto': p.revision_veredicto,
        'revision_resumen': p.revision_resumen,
        'revision_json': p.revision_json,
        'revision_at': p.revision_at.isoformat() if p.revision_at else None,
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
    """Actualiza estado / notas / published_url / metricas de una publicación.

    Body JSON: {"estado": "...", "published_url": "...", "notas": "...",
    "metricas": {...}} (todos opcionales; solo se tocan los campos presentes).
    `metricas` es el objeto completo del contrato H-067 (REPLACE simple).
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

    if 'metricas' in payload:
        metricas = payload.get('metricas')
        if not isinstance(metricas, dict):
            return JsonResponse({'error': 'metricas debe ser un objeto JSON'}, status=400)
        # Contrato H-067 (docs/CONTRATO_H-067_METRICAS.md): REPLACE simple — el
        # merge del historial de snapshots ya viene hecho por la cosecha Go.
        pub.metricas = metricas
        cambios.append('metricas')

    if not cambios:
        return JsonResponse({'error': 'Nada que actualizar (enviar estado, published_url, notas o metricas)'}, status=400)

    pub.save(update_fields=cambios + ['updated_at'])
    logger.info(f'publicacion_actualizar: #{pub_id} campos {cambios}')
    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})


@csrf_exempt
@require_http_methods(['GET'])
def publicacion_detalle(request, pub_id: int):
    """Devuelve una publicación (para polling del estado de revisión)."""
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)
    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return JsonResponse({'error': f'Publicación {pub_id} no existe'}, status=404)
    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})


def _run_revision_background(pub_id: int, indice=None):
    """Corre la revisión IA en un thread (la llamada al modelo tarda más que
    el timeout del cliente HTTP del backend Go — por eso va fire-and-forget y
    Angélica ve el resultado por polling). Si `indice` viene, revisa esa
    historia (segmento) contra su propio texto; si no, la publicación entera."""
    try:
        from .revision_service import revisar_material, revisar_segmento
        pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
        if pub is None:
            return
        if indice is not None:
            revisar_segmento(pub, indice)
        else:
            revisar_material(pub)
    except Exception as exc:  # noqa: BLE001
        logger.error(f'_run_revision_background #{pub_id} seg={indice}: {exc}', exc_info=True)
        try:
            _marcar_segmento_sin_revisar(pub_id, indice)
        except Exception:  # noqa: BLE001
            pass


def _marcar_segmento_sin_revisar(pub_id, indice):
    """Deja el veredicto en 'sin_revisar' si la revisión reventó, a nivel
    publicación o del segmento que corresponda."""
    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return
    if indice is None:
        pub.revision_veredicto = 'sin_revisar'
        pub.save(update_fields=['revision_veredicto', 'updated_at'])
        return
    segmentos = pub.segmentos or []
    for s in segmentos:
        if isinstance(s, dict) and s.get('indice') == indice:
            s['revision_veredicto'] = 'sin_revisar'
    pub.segmentos = segmentos
    pub.save(update_fields=['segmentos', 'updated_at'])


@csrf_exempt
@require_http_methods(['POST'])
def publicacion_material(request, pub_id: int):
    """Recibe fotos o video (multipart, campo 'files'), los sube a Cloudinary, y
    dispara la revisión IA en background. Responde de inmediato con estado
    'revisando'. Video (.mp4/.mov) solo en piezas tipo 'reel' (H-065/H-066 F2):
    con `segmento=<indice>` es el micro-clip de esa toma; sin él, el reel entero.
    """
    if not _api_key_ok(request):
        return JsonResponse({'error': 'X-API-KEY inválida o ausente'}, status=401)

    pub = PublicacionPlanificada.objects.filter(id=pub_id).first()
    if pub is None:
        return JsonResponse({'error': f'Publicación {pub_id} no existe'}, status=404)

    # Índice de historia (segmento) opcional. Si viene, la foto y su revisión
    # van a ESA historia; si no, a la publicación entera (piezas de 1 imagen).
    indice = None
    seg = None
    seg_raw = (request.POST.get('segmento') or '').strip()
    if seg_raw:
        try:
            indice = int(seg_raw)
        except ValueError:
            return JsonResponse({'error': 'segmento inválido'}, status=400)
        seg = next((s for s in (pub.segmentos or []) if isinstance(s, dict) and s.get('indice') == indice), None)
        if seg is None:
            return JsonResponse({'error': f'La publicación no tiene la historia {indice}'}, status=400)

    archivos = request.FILES.getlist('files') or request.FILES.getlist('file')
    if not archivos:
        return JsonResponse({'error': 'No se recibió ningún archivo (campo "files")'}, status=400)

    try:
        from cloudinary_storage.storage import MediaCloudinaryStorage
        storage = MediaCloudinaryStorage()
    except Exception as exc:  # noqa: BLE001
        logger.error(f'publicacion_material: storage Cloudinary no disponible ({exc})')
        return JsonResponse({'error': 'Almacenamiento de imágenes no disponible'}, status=503)

    nuevas_urls, nuevas_meta = [], []
    for f in archivos:
        ext = ('.' + f.name.rsplit('.', 1)[-1].lower()) if '.' in f.name else ''
        if ext in _EXT_VIDEO:
            # Rama video (H-065/H-066 F2). La revisión posterior deriva los
            # fotogramas por URL (so_<seg> + .jpg), sin ffmpeg.
            if pub.tipo != 'reel':
                return JsonResponse(
                    {'error': f'{f.name}: el video solo se acepta en reels (esta pieza es "{pub.tipo}").'},
                    status=400,
                )
            if f.size and f.size > _MAX_BYTES_VIDEO:
                return JsonResponse({'error': f'{f.name} supera el máximo de 100 MB para video.'}, status=400)
            nombre = f'publicaciones/{pub.semana_inicio.isoformat()}/{uuid.uuid4().hex}{ext}'
            try:
                item = _subir_video_cloudinary(f, nombre)
            except Exception as exc:  # noqa: BLE001
                logger.error(f'publicacion_material: falló subir video {f.name} ({exc})')
                return JsonResponse({'error': f'No se pudo subir {f.name}'}, status=502)
            nuevas_urls.append(item['url'])
            nuevas_meta.append(item)
            continue
        if ext not in _EXT_IMAGEN:
            return JsonResponse(
                {'error': f'Formato no soportado: {f.name}. Imágenes ({", ".join(sorted(_EXT_IMAGEN))}) '
                          f'o video en reels ({", ".join(sorted(_EXT_VIDEO))}).'},
                status=400,
            )
        if f.size and f.size > _MAX_BYTES:
            return JsonResponse({'error': f'{f.name} supera el máximo de 16 MB.'}, status=400)
        # Medir ancho×alto ANTES de subir (mientras el archivo está en memoria).
        dims = _medir_imagen(f)
        nombre = f'publicaciones/{pub.semana_inicio.isoformat()}/{uuid.uuid4().hex}{ext}'
        try:
            guardado = storage.save(nombre, f)
            url = storage.url(guardado)
        except Exception as exc:  # noqa: BLE001
            logger.error(f'publicacion_material: falló subir {f.name} ({exc})')
            return JsonResponse({'error': f'No se pudo subir {f.name}'}, status=502)
        nuevas_urls.append(url)
        nuevas_meta.append({'url': url, **dims})

    if seg is not None:
        # Foto y revisión de ESTA historia.
        seg['material_urls'] = list(seg.get('material_urls') or []) + nuevas_urls
        seg['material_meta'] = list(seg.get('material_meta') or []) + nuevas_meta
        seg['revision_veredicto'] = 'revisando'
        pub.segmentos = pub.segmentos  # ya mutado in-place; explícito para claridad
        pub.save(update_fields=['segmentos', 'updated_at'])
    else:
        pub.material_urls = list(pub.material_urls or []) + nuevas_urls
        pub.material_meta = list(pub.material_meta or []) + nuevas_meta
        pub.revision_veredicto = 'revisando'
        pub.save(update_fields=['material_urls', 'material_meta', 'revision_veredicto', 'updated_at'])

    from threading import Thread
    Thread(target=_run_revision_background, args=(pub.id, indice), daemon=True).start()

    return JsonResponse({'success': True, 'publicacion': _serialize(pub)})
