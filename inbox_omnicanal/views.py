"""Bandeja omnicanal — endpoints (H-016). Consumidos por aremko-cli / Go.

Auth: header X-API-Key (LUNA_API_KEY), mismo esquema que /api/whatsapp/*.

Rutas:
  POST /api/instagram/inbound                                  → guarda un DM de Instagram
  GET  /api/inbox/conversations/                               → lista unificada WhatsApp + Instagram
  GET  /api/inbox/conversation/?canal=&external_id=            → hilo de una conversación
  POST /api/inbox/conversations/<canal>/<external_id>/marcar-atendido/

Instagram es REACTIVO (ventana 24h, sin plantillas). Outbound/responder = H-017;
adjuntos = Fase 5. Aquí solo persistencia + reads channel-aware.
"""

import json
import logging
import mimetypes
import os
import uuid
from datetime import datetime, timezone as dt_tz

from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.csrf import csrf_exempt

from .logic import truthy as _truthy, external_id_conversacion
from .models import ChannelMessage

logger = logging.getLogger(__name__)

_MIN_TS = datetime.min.replace(tzinfo=dt_tz.utc)
IG_ACCOUNT_ID = '17841400756478364'  # IG Business Account de Aremko (recipient en inbound)

# Adjuntos (Fase 5), mismo esquema que WhatsApp.
_MEDIA_TYPES = {'image', 'video', 'audio', 'voice', 'share', 'story_mention', 'sticker', 'document'}
_MEDIA_MAX_BYTES_DEFAULT = 16 * 1024 * 1024  # 16 MB


def _media_label(msg_type, original_filename=''):
    """Etiqueta de preview para un adjunto sin texto (lista de conversaciones)."""
    t = (msg_type or '').lower()
    if t == 'image':
        return '📷 Foto'
    if t == 'video':
        return '🎥 Video'
    if t in ('audio', 'voice'):
        return '🎤 Nota de voz'
    if t == 'sticker':
        return '🟢 Sticker'
    if t == 'story_mention':
        return '📸 Te mencionó en una historia'
    if t == 'share':
        return '🔗 Compartió una publicación'
    if t == 'document':
        nombre = (original_filename or '').strip()
        return f'📄 {nombre}' if nombre else '📄 Documento'
    return ''


def _guess_extension(original_filename, mime_type):
    """Extensión del archivo: primero del nombre original, luego del mime_type."""
    _, ext = os.path.splitext(original_filename or '')
    if ext:
        return ext[:12]
    guessed = mimetypes.guess_extension((mime_type or '').split(';')[0].strip())
    return guessed or ''


def _media_url(request, m):
    """URL absoluta del adjunto (el frontend vive en otro dominio). Cloudinary ya
    devuelve absoluta; build_absolute_uri la deja igual."""
    if not getattr(m, 'media_file', None):
        return None
    try:
        return request.build_absolute_uri(m.media_file.url)
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_luna_key(request):
    """Valida X-API-Key contra settings.LUNA_API_KEY (igual que /api/whatsapp/*)."""
    expected = getattr(settings, 'LUNA_API_KEY', None)
    provided = request.headers.get('X-API-Key') or request.META.get('HTTP_X_API_KEY')
    if not expected or not provided or provided != expected:
        return JsonResponse({'error': 'No autorizado. Se requiere header X-API-Key válido.'}, status=401)
    return None


def _parse_ts(value):
    """Acepta epoch (seg) o ISO; devuelve datetime aware. Default: ahora."""
    if value in (None, ''):
        return timezone.now()
    try:
        return datetime.fromtimestamp(int(float(value)), tz=dt_tz.utc)
    except (ValueError, TypeError, OSError):
        pass
    parsed = parse_datetime(str(value))
    if parsed:
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed, dt_tz.utc)
    return timezone.now()


def _limpiar_pendientes_channel(canal, external_id):
    """Saca de 'pendientes' una conversación de ChannelMessage: limpia `requiere_atencion`
    de sus entrantes. Devuelve cuántos se limpiaron. Lo usan marcar-atendido y el eco de
    salida (responder = la conversación deja de estar pendiente, paridad con WhatsApp)."""
    return ChannelMessage.objects.filter(
        canal=canal, external_id=external_id, direction='in', requiere_atencion=True,
    ).update(requiere_atencion=False)


def _nombres_clientes(cliente_ids):
    """{id: nombre} para un conjunto de ventas.Cliente.id (resuelto perezosamente)."""
    ids = {i for i in cliente_ids if i}
    if not ids:
        return {}
    try:
        from ventas.models import Cliente
        return {c.id: c.nombre for c in Cliente.objects.filter(id__in=ids).only('id', 'nombre')}
    except Exception:  # noqa: BLE001 — la bandeja no debe romperse si falla el lookup
        logger.exception('Inbox: no se pudieron resolver nombres de cliente')
        return {}


# ---------------------------------------------------------------------------
# Inbound Instagram
# ---------------------------------------------------------------------------

@csrf_exempt
def instagram_inbound(request):
    """POST /api/instagram/inbound — persiste un DM de Instagram (texto).

    Conversación = (instagram, external_id) donde external_id es el IGSID del CLIENTE
    (el que no es la cuenta de Aremko). `is_echo=true` = mensaje que envió la propia
    cuenta → saliente, no marca pendiente. Idempotente por `ig_message_id`.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'método no permitido'}, status=405)
    err = _check_luna_key(request)
    if err:
        return err

    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    ig_message_id = (data.get('ig_message_id') or '').strip()
    from_igsid = (data.get('from_igsid') or '').strip()
    to_igsid = (data.get('to_igsid') or '').strip()
    if not ig_message_id or not from_igsid:
        return JsonResponse({'error': 'ig_message_id y from_igsid son requeridos'}, status=400)

    is_echo = _truthy(data.get('is_echo'))
    direction = 'out' if is_echo else 'in'
    # La conversación se identifica por el IGSID del cliente (no la cuenta de Aremko).
    external_id = external_id_conversacion(from_igsid, to_igsid, is_echo)
    if not external_id:
        return JsonResponse({'error': 'no se pudo determinar el IGSID del cliente'}, status=400)

    obj, created = ChannelMessage.objects.get_or_create(
        external_message_id=ig_message_id,
        defaults=dict(
            canal='instagram',
            external_id=external_id[:120],
            direction=direction,
            body=(data.get('text') or ''),
            msg_type=(data.get('msg_type') or 'text'),
            timestamp=_parse_ts(data.get('timestamp')),
            contact_name=(data.get('contact_name') or '')[:200],
            requiere_atencion=(direction == 'in'),
        ),
    )
    # Un saliente (eco = la cuenta respondió por IG) saca la conversación de pendientes,
    # igual que el outbound de WhatsApp. Solo en el primer registro (idempotente).
    pendientes_limpiados = 0
    if created and obj.direction == 'out':
        pendientes_limpiados = _limpiar_pendientes_channel('instagram', obj.external_id)

    return JsonResponse({
        'ok': True,
        'message_id': obj.id,
        'canal': 'instagram',
        'external_id': obj.external_id,
        'direction': obj.direction,
        'requiere_atencion': obj.requiere_atencion,
        'pendientes_limpiados': pendientes_limpiados,
        'duplicate': (not created),
    })


@csrf_exempt
def messenger_inbound(request):
    """POST /api/messenger/inbound — persiste un mensaje de Facebook Messenger (H-023).

    Conversación = (messenger, external_id) donde external_id es el PSID del CLIENTE
    (el que no es la Página de Aremko: 555157687911449). `is_echo=true` = mensaje que
    envió la propia página → saliente, no marca pendiente. Idempotente por `fb_message_id`.
    Mirror exacto de H-016 Instagram, pero con canal='messenger' y campos renombrados.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'método no permitido'}, status=405)
    err = _check_luna_key(request)
    if err:
        return err

    try:
        data = json.loads(request.body or '{}')
    except (ValueError, TypeError):
        return JsonResponse({'error': 'JSON inválido'}, status=400)

    fb_message_id = (data.get('fb_message_id') or '').strip()
    from_psid = (data.get('from_psid') or '').strip()
    to_page_id = (data.get('to_page_id') or '').strip()
    if not fb_message_id or not from_psid:
        return JsonResponse({'error': 'fb_message_id y from_psid son requeridos'}, status=400)

    is_echo = _truthy(data.get('is_echo'))
    direction = 'out' if is_echo else 'in'
    # La conversación se identifica por el PSID del cliente (no la Página 555157687911449).
    # Esperamos que aremko-cli pase from_psid ≠ 555157687911449, pero validamos.
    if from_psid == '555157687911449':
        return JsonResponse({'error': 'PSID no puede ser la Página de Aremko'}, status=400)
    external_id = from_psid  # El PSID del cliente es la identidad de la conversación

    obj, created = ChannelMessage.objects.get_or_create(
        external_message_id=fb_message_id,
        defaults=dict(
            canal='messenger',
            external_id=external_id[:120],
            direction=direction,
            body=(data.get('text') or ''),
            msg_type=(data.get('msg_type') or 'text'),
            timestamp=_parse_ts(data.get('timestamp')),
            contact_name=(data.get('contact_name') or '')[:200],
            requiere_atencion=(direction == 'in'),
        ),
    )
    # Un saliente (eco = la página respondió) saca la conversación de pendientes,
    # igual que IG. Solo en el primer registro (idempotente).
    pendientes_limpiados = 0
    if created and obj.direction == 'out':
        pendientes_limpiados = _limpiar_pendientes_channel('messenger', obj.external_id)

    return JsonResponse({
        'ok': True,
        'message_id': obj.id,
        'canal': 'messenger',
        'external_id': obj.external_id,
        'direction': obj.direction,
        'requiere_atencion': obj.requiere_atencion,
        'pendientes_limpiados': pendientes_limpiados,
        'duplicate': (not created),
    })


@csrf_exempt
def instagram_inbound_media(request):
    """POST /api/instagram/inbound-media (multipart) — DM de Instagram con adjunto (Fase 5).

    aremko-cli descarga los bytes del media temporal de IG (con el token) y los sube acá.
    Guardamos el archivo (nombre UUID) en el mismo storage RAW de Cloudinary que WhatsApp.
    Idempotente por ig_message_id; is_echo→saliente (limpia pendientes); conversación = IGSID
    del cliente.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'método no permitido'}, status=405)
    err = _check_luna_key(request)
    if err:
        return err

    ig_message_id = (request.POST.get('ig_message_id') or '').strip()
    from_igsid = (request.POST.get('from_igsid') or '').strip()
    to_igsid = (request.POST.get('to_igsid') or '').strip()
    if not ig_message_id or not from_igsid:
        return JsonResponse({'error': 'ig_message_id y from_igsid son requeridos'}, status=400)

    upload = request.FILES.get('file')
    if not upload:
        return JsonResponse({'error': "Falta el archivo 'file' (multipart/form-data)"}, status=400)

    # Tope de tamaño: rechaza antes de subir a Cloudinary (mismo tope que WhatsApp).
    max_bytes = int(getattr(settings, 'WHATSAPP_MEDIA_MAX_BYTES', _MEDIA_MAX_BYTES_DEFAULT))
    size = getattr(upload, 'size', 0) or 0
    if size > max_bytes:
        return JsonResponse({
            'error': 'Archivo demasiado grande', 'max_bytes': max_bytes,
            'max_mb': round(max_bytes / (1024 * 1024), 1), 'size_bytes': size,
        }, status=413)

    is_echo = _truthy(request.POST.get('is_echo'))
    direction = 'out' if is_echo else 'in'
    external_id = external_id_conversacion(from_igsid, to_igsid, is_echo)
    if not external_id:
        return JsonResponse({'error': 'no se pudo determinar el IGSID del cliente'}, status=400)

    msg_type = (request.POST.get('type') or 'document').lower()[:30]
    if msg_type not in _MEDIA_TYPES:
        msg_type = 'document'
    caption = request.POST.get('caption') or ''
    mime_type = (request.POST.get('mime_type') or getattr(upload, 'content_type', '') or '')[:120]
    original_filename = (request.POST.get('filename') or getattr(upload, 'name', '') or '')[:255]
    contact_name = (request.POST.get('contact_name') or '')[:200]
    ts = _parse_ts(request.POST.get('timestamp'))

    # Idempotencia por ig_message_id.
    existing = ChannelMessage.objects.filter(external_message_id=ig_message_id).first()
    if existing:
        return JsonResponse({
            'ok': True, 'duplicate': True, 'message_id': existing.id,
            'canal': 'instagram', 'external_id': existing.external_id,
            'media_url': _media_url(request, existing),
        })

    # Nombre con UUID + extensión (evita colisiones y el nombre del cliente).
    ext = _guess_extension(original_filename, mime_type)
    stored_name = f"{uuid.uuid4().hex}{ext}"

    msg = ChannelMessage(
        canal='instagram', external_id=external_id[:120], external_message_id=ig_message_id,
        direction=direction, body=caption, msg_type=msg_type, timestamp=ts,
        contact_name=contact_name, requiere_atencion=(direction == 'in'),
        mime_type=mime_type, original_filename=original_filename,
    )
    msg.media_file.save(stored_name, upload, save=False)  # save=False: persistir una sola vez
    msg.save()

    pendientes_limpiados = 0
    if direction == 'out':
        pendientes_limpiados = _limpiar_pendientes_channel('instagram', msg.external_id)

    return JsonResponse({
        'ok': True, 'message_id': msg.id, 'canal': 'instagram',
        'external_id': msg.external_id, 'direction': msg.direction,
        'requiere_atencion': msg.requiere_atencion,
        'pendientes_limpiados': pendientes_limpiados,
        'media_url': _media_url(request, msg),
    })


# ---------------------------------------------------------------------------
# Reads unificados (WhatsApp legacy + Instagram)
# ---------------------------------------------------------------------------

def _agg_whatsapp():
    """Una fila por teléfono desde ventas.WhatsAppMessage (canal whatsapp)."""
    from django.db.models import Max, Count, Q
    from ventas.models import WhatsAppMessage
    filas = WhatsAppMessage.objects.values('phone').annotate(
        ultimo_ts=Max('timestamp'),
        total=Count('id'),
        req=Count('id', filter=Q(direction='in', requiere_atencion=True)),
    )
    return [{'canal': 'whatsapp', 'external_id': f['phone'], 'ultimo_ts': f['ultimo_ts'],
             'total': f['total'], 'req': f['req']} for f in filas]


def _agg_instagram():
    """Una fila por IGSID desde ChannelMessage (canal instagram)."""
    from django.db.models import Max, Count, Q
    filas = ChannelMessage.objects.filter(canal='instagram').values('external_id').annotate(
        ultimo_ts=Max('timestamp'),
        total=Count('id'),
        req=Count('id', filter=Q(direction='in', requiere_atencion=True)),
    )
    return [{'canal': 'instagram', 'external_id': f['external_id'], 'ultimo_ts': f['ultimo_ts'],
             'total': f['total'], 'req': f['req']} for f in filas]


def _detalle_whatsapp(external_ids):
    """{phone: {preview, direction, contact_name, cliente_id, cliente_nombre}} para la página."""
    from ventas.models import WhatsAppMessage
    out = {}
    if not external_ids:
        return out
    for m in (WhatsAppMessage.objects.filter(phone__in=external_ids)
              .select_related('cliente').order_by('phone', '-timestamp')):
        if m.phone in out:
            continue
        cli = m.cliente if m.cliente_id else None
        preview = m.body or (_media_label(m) if m.media_file else '')
        out[m.phone] = {
            'preview': preview, 'direction': m.direction,
            'contact_name': m.contact_name or None,
            'cliente_id': cli.id if cli else None,
            'cliente_nombre': (cli.nombre if cli and cli.nombre else None),
        }
    return out


def _media_label(m):
    etiquetas = {'image': '📷 Foto', 'video': '🎥 Video', 'audio': '🎤 Audio', 'document': '📄 Documento'}
    return etiquetas.get(m.msg_type, '📎 Adjunto')


def _detalle_instagram(external_ids):
    """{igsid: {preview, direction, contact_name, cliente_id, cliente_nombre}} para la página."""
    out = {}
    if not external_ids:
        return out
    ultimos = {}
    cliente_por_ext = {}
    nombre_por_ext = {}  # H-018: el nombre de la conversación = último contact_name NO vacío
    for m in (ChannelMessage.objects.filter(canal='instagram', external_id__in=external_ids)
              .order_by('external_id', '-timestamp')):
        if m.external_id not in ultimos:
            ultimos[m.external_id] = m
        # Ordenado por -timestamp → el primer contact_name no vacío es el más reciente.
        # Así un eco saliente sin nombre (la cuenta respondió) no esconde el del cliente.
        if m.external_id not in nombre_por_ext and m.contact_name:
            nombre_por_ext[m.external_id] = m.contact_name
        if m.external_id not in cliente_por_ext and m.cliente_id:
            cliente_por_ext[m.external_id] = m.cliente_id
    nombres = _nombres_clientes(cliente_por_ext.values())
    for ext, m in ultimos.items():
        cid = cliente_por_ext.get(ext)
        out[ext] = {
            'preview': m.body or (_media_label(m.msg_type, m.original_filename) if m.media_file else ''),
            'direction': m.direction,
            'contact_name': nombre_por_ext.get(ext),
            'cliente_id': cid,
            'cliente_nombre': nombres.get(cid),
        }
    return out


def _agg_messenger():
    """Una fila por PSID desde ChannelMessage (canal messenger)."""
    from django.db.models import Max, Count, Q
    filas = ChannelMessage.objects.filter(canal='messenger').values('external_id').annotate(
        ultimo_ts=Max('timestamp'),
        total=Count('id'),
        req=Count('id', filter=Q(direction='in', requiere_atencion=True)),
    )
    return [{'canal': 'messenger', 'external_id': f['external_id'], 'ultimo_ts': f['ultimo_ts'],
             'total': f['total'], 'req': f['req']} for f in filas]


def _detalle_messenger(external_ids):
    """{psid: {preview, direction, contact_name, cliente_id, cliente_nombre}} para la página."""
    out = {}
    if not external_ids:
        return out
    ultimos = {}
    cliente_por_ext = {}
    nombre_por_ext = {}  # H-023: el nombre de la conversación = último contact_name NO vacío
    for m in (ChannelMessage.objects.filter(canal='messenger', external_id__in=external_ids)
              .order_by('external_id', '-timestamp')):
        if m.external_id not in ultimos:
            ultimos[m.external_id] = m
        # Ordenado por -timestamp → el primer contact_name no vacío es el más reciente.
        # Así un eco saliente sin nombre (la página respondió) no esconde el del cliente.
        if m.external_id not in nombre_por_ext and m.contact_name:
            nombre_por_ext[m.external_id] = m.contact_name
        if m.external_id not in cliente_por_ext and m.cliente_id:
            cliente_por_ext[m.external_id] = m.cliente_id
    nombres = _nombres_clientes(cliente_por_ext.values())
    for ext, m in ultimos.items():
        cid = cliente_por_ext.get(ext)
        # Fallback: si no hay nombre, mostrar "Cliente Messenger #PSID"
        nombre = nombre_por_ext.get(ext) or f'Cliente Messenger #{ext}'
        out[ext] = {
            'preview': m.body or (_media_label(m.msg_type, m.original_filename) if m.media_file else ''),
            'direction': m.direction,
            'contact_name': nombre,
            'cliente_id': cid,
            'cliente_nombre': nombres.get(cid),
        }
    return out


def conversations(request):
    """GET /api/inbox/conversations/ — lista unificada WhatsApp + Instagram + Messenger.

    Una fila por conversación (canal, external_id). Orden: pendientes primero
    (H-006) cruzando todos los canales, luego por recencia, ANTES del corte [:limit].
    """
    err = _check_luna_key(request)
    if err:
        return err

    solo_pendientes = _truthy(request.GET.get('solo_pendientes'))
    canal_filtro = (request.GET.get('canal') or '').strip().lower()
    try:
        limit = min(max(int(request.GET.get('limit', 50)), 1), 200)
    except (ValueError, TypeError):
        limit = 50

    agg = []
    if canal_filtro in ('', 'whatsapp'):
        agg += _agg_whatsapp()
    if canal_filtro in ('', 'instagram'):
        agg += _agg_instagram()
    if canal_filtro in ('', 'messenger'):
        agg += _agg_messenger()

    agg.sort(key=lambda a: (a['req'] > 0, a['ultimo_ts'] or _MIN_TS), reverse=True)
    if solo_pendientes:
        agg = [a for a in agg if a['req'] > 0]
    page = agg[:limit]

    wa_ids = [a['external_id'] for a in page if a['canal'] == 'whatsapp']
    ig_ids = [a['external_id'] for a in page if a['canal'] == 'instagram']
    messenger_ids = [a['external_id'] for a in page if a['canal'] == 'messenger']
    det_wa = _detalle_whatsapp(wa_ids)
    det_ig = _detalle_instagram(ig_ids)
    det_messenger = _detalle_messenger(messenger_ids)

    out = []
    for a in page:
        if a['canal'] == 'whatsapp':
            det = det_wa.get(a['external_id'], {})
        elif a['canal'] == 'instagram':
            det = det_ig.get(a['external_id'], {})
        else:  # messenger
            det = det_messenger.get(a['external_id'], {})
        out.append({
            'canal': a['canal'],
            'external_id': a['external_id'],
            'phone': a['external_id'] if a['canal'] == 'whatsapp' else None,
            'cliente_id': det.get('cliente_id'),
            'cliente_nombre': det.get('cliente_nombre'),
            'contact_name': det.get('contact_name'),
            'ultimo_mensaje': det.get('preview', ''),
            'ultimo_direction': det.get('direction'),
            'ultimo_timestamp': a['ultimo_ts'].isoformat() if a['ultimo_ts'] else None,
            'sin_responder': a['req'],
            'requiere_atencion': a['req'] > 0,
            'total_mensajes': a['total'],
        })

    return JsonResponse({'count': len(out), 'conversations': out})


def conversation(request):
    """GET /api/inbox/conversation/?canal=&external_id= — hilo de una conversación.

    Compat: si llega `?phone=` sin canal, se asume whatsapp. Cada mensaje trae `canal`.
    """
    err = _check_luna_key(request)
    if err:
        return err

    canal = (request.GET.get('canal') or '').strip().lower()
    external_id = (request.GET.get('external_id') or '').strip()
    phone = (request.GET.get('phone') or '').strip()
    if not canal and phone:
        canal, external_id = 'whatsapp', phone
    if not external_id:
        return JsonResponse({'error': 'external_id (o phone) requerido'}, status=400)
    try:
        limit = min(int(request.GET.get('limit', 50)), 500)
    except (ValueError, TypeError):
        limit = 50

    if canal == 'instagram':
        msgs = list(ChannelMessage.objects.filter(canal='instagram', external_id=external_id)
                    .order_by('-timestamp')[:limit])
        msgs.reverse()
        cliente_id = next((m.cliente_id for m in msgs if m.cliente_id), None)
        contact_name = next((m.contact_name for m in reversed(msgs) if m.contact_name), '')
        return JsonResponse({
            'canal': 'instagram',
            'external_id': external_id,
            'cliente_id': cliente_id,
            'contact_name': contact_name or None,
            'count': len(msgs),
            'messages': [{
                'external_message_id': m.external_message_id,
                'canal': 'instagram',
                'direction': m.direction,
                'body': m.body,
                'type': m.msg_type,
                'status': m.status or None,
                'timestamp': m.timestamp.isoformat(),
                'media_url': _media_url(request, m),
                'mime_type': m.mime_type or None,
                'filename': m.original_filename or None,
            } for m in msgs],
            # H-019: borrador de IA para IG, lazy (opt-in ?sugerencia=1), mismo shape que WA.
            'sugerencia_agente': (
                _sugerencia_instagram(external_id)
                if _truthy(request.GET.get('sugerencia', '0')) else None
            ),
        })

    if canal == 'messenger':
        msgs = list(ChannelMessage.objects.filter(canal='messenger', external_id=external_id)
                    .order_by('-timestamp')[:limit])
        msgs.reverse()
        cliente_id = next((m.cliente_id for m in msgs if m.cliente_id), None)
        contact_name = next((m.contact_name for m in reversed(msgs) if m.contact_name), '')
        return JsonResponse({
            'canal': 'messenger',
            'external_id': external_id,
            'cliente_id': cliente_id,
            'contact_name': contact_name or None,
            'count': len(msgs),
            'messages': [{
                'external_message_id': m.external_message_id,
                'canal': 'messenger',
                'direction': m.direction,
                'body': m.body,
                'type': m.msg_type,
                'status': m.status or None,
                'timestamp': m.timestamp.isoformat(),
                'media_url': _media_url(request, m),
                'mime_type': m.mime_type or None,
                'filename': m.original_filename or None,
            } for m in msgs],
        })

    if canal == 'whatsapp':
        from ventas.models import WhatsAppMessage
        msgs = list(WhatsAppMessage.objects.filter(phone=external_id).order_by('-timestamp')[:limit])
        msgs.reverse()
        return JsonResponse({
            'canal': 'whatsapp',
            'external_id': external_id,
            'phone': external_id,
            'count': len(msgs),
            'messages': [{
                'external_message_id': m.wa_message_id,
                'canal': 'whatsapp',
                'direction': m.direction,
                'body': m.body,
                'type': m.msg_type,
                'status': m.status or None,
                'timestamp': m.timestamp.isoformat(),
            } for m in msgs],
            'sugerencia_agente': _sugerencia_whatsapp(external_id, request),
        })

    return JsonResponse({'error': f'canal no soportado: {canal!r}'}, status=400)


def _historial_instagram(external_id, antes_de_ts, window):
    """Historial reciente de una conversación IG como texto, igual formato que WhatsApp."""
    msgs = list(
        ChannelMessage.objects
        .filter(canal='instagram', external_id=external_id, timestamp__lt=antes_de_ts)
        .order_by('-timestamp')[:window]
    )
    msgs.reverse()
    lineas = []
    for m in msgs:
        cuerpo = (m.body or '').strip() or f'({m.msg_type})'
        quien = 'Cliente' if m.direction == 'in' else 'Aremko'
        lineas.append(f'[{quien}]: {cuerpo}')
    return '\n'.join(lineas)


def _contexto_saludo_instagram(external_id, entrante_timestamp):
    """(estado_saludo, nombre) para una conversación de Instagram. Agnóstico de WhatsApp.

    Busca el mensaje anterior más reciente (excluye reacciones). Devuelve ('', '') si falla.
    """
    try:
        from whatsapp_agent.prompt import clasificar_saludo, saneo_nombre
        previo = (
            ChannelMessage.objects
            .filter(canal='instagram', external_id=external_id, timestamp__lt=entrante_timestamp)
            .exclude(msg_type='reaction')
            .order_by('-timestamp')
            .values_list('timestamp', flat=True)
            .first()
        )
        hay_previos = previo is not None
        dias = (entrante_timestamp - previo).days if hay_previos else None
        estado = clasificar_saludo(hay_previos, dias)

        nombre = saneo_nombre(ChannelMessage.objects
                              .filter(canal='instagram', external_id=external_id)
                              .values_list('contact_name', flat=True)
                              .first() or '')
        return estado, nombre
    except Exception:  # noqa: BLE001 — el saludo nunca debe tumbar el borrador
        logger.exception('Inbox IG: no se pudo calcular el contexto de saludo')
        return '', ''


def _sugerencia_instagram(external_id):
    """Borrador del agente IA para una conversación de Instagram (H-019).

    Reusa `whatsapp_agent._producir_borrador` (grounding/config/escalamiento; agnóstico
    de teléfono). Devuelve el MISMO shape que WhatsApp, o None si: el agente está apagado,
    no hay entrante IG pendiente, o algo falla. Lazy y sin caché (v1). El caller decide
    cuándo pedirlo (`&sugerencia=1`).
    """
    try:
        from whatsapp_agent.agent import _producir_borrador, get_config
        config = get_config()
        if not config.activo:
            return None
        entrante = (
            ChannelMessage.objects
            .filter(canal='instagram', external_id=external_id,
                    direction='in', requiere_atencion=True)
            .order_by('-timestamp')
            .first()
        )
        if entrante is None:
            return None
        historial = _historial_instagram(external_id, entrante.timestamp, config.history_window)
        saludo_estado, saludo_nombre = _contexto_saludo_instagram(external_id, entrante.timestamp)
        d = _producir_borrador(config, entrante.body, historial,
                               saludo_estado=saludo_estado, saludo_nombre=saludo_nombre)
        return {
            'texto': d['texto'],
            'escalar': d['escalar'],
            'motivo': d['motivo'],
            'modo': config.modo,
            'modelo': d['modelo'],
            'error': d['error'],
            'generada_at': timezone.now().isoformat(),
            'responde_a': entrante.external_message_id,
        }
    except Exception:  # noqa: BLE001 — el agente es opcional; nunca tumbar el hilo
        logger.exception('Inbox: fallo generando sugerencia IG para %s', external_id)
        return None


def _sugerencia_whatsapp(phone, request):
    """Reusa el borrador del agente IA de WhatsApp (opt-in con ?sugerencia=1)."""
    if not _truthy(request.GET.get('sugerencia', '0')):
        return None
    try:
        from whatsapp_agent.agent import generar_sugerencia, sugerencia_to_dict
        return sugerencia_to_dict(generar_sugerencia(phone))
    except Exception:  # noqa: BLE001 — el agente es opcional; nunca tumbar el hilo
        logger.exception('Inbox: fallo generando sugerencia WA para %s', phone)
        return None


@csrf_exempt
def marcar_atendido(request, canal, external_id):
    """POST /api/inbox/conversations/<canal>/<external_id>/marcar-atendido/ (H-005 channel-aware)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'método no permitido'}, status=405)
    err = _check_luna_key(request)
    if err:
        return err

    canal = (canal or '').strip().lower()
    external_id = (external_id or '').strip()
    if canal == 'instagram':
        actualizado = _limpiar_pendientes_channel('instagram', external_id)
    elif canal == 'whatsapp':
        from ventas.models import WhatsAppMessage
        actualizado = WhatsAppMessage.objects.filter(
            phone=external_id[:20], direction='in', requiere_atencion=True,
        ).update(requiere_atencion=False)
    else:
        return JsonResponse({'error': f'canal no soportado: {canal!r}'}, status=400)

    return JsonResponse({
        'success': True, 'canal': canal, 'external_id': external_id,
        'actualizado': bool(actualizado), 'mensajes_actualizados': actualizado,
    })
